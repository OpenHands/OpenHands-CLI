"""Tests for utility functions."""

import json
from argparse import Namespace
from unittest.mock import patch

import pytest
from acp.schema import EnvVariable, McpServerStdio

from openhands.sdk.event import MessageEvent, SystemPromptEvent
from openhands.sdk.llm import Message, TextContent
from openhands_cli.acp_impl.utils import convert_acp_mcp_servers_to_agent_format
from openhands_cli.utils import (
    conversation_has_delegate_tool_events,
    create_seeded_instructions_from_args,
    get_default_cli_tools,
    json_callback,
    should_set_litellm_extra_body,
)


def test_get_default_cli_tools_returns_task_tool_set_by_default():
    """Test get_default_cli_tools uses TaskToolSet by default for new conversations."""
    tools = get_default_cli_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {"terminal", "file_editor", "task_tracker", "task_tool_set"}


def test_get_default_cli_tools_returns_delegate_when_requested():
    """Test that get_default_cli_tools uses DelegateTool when use_delegate_tool=True."""
    tools = get_default_cli_tools(use_delegate_tool=True)
    tool_names = {t.name for t in tools}
    assert tool_names == {"terminal", "file_editor", "task_tracker", "delegate"}


def test_should_set_litellm_extra_body_for_openhands():
    """Test that litellm_extra_body is set for openhands models."""
    assert should_set_litellm_extra_body("openhands/claude-sonnet-4-5-20250929")
    assert should_set_litellm_extra_body("openhands/gpt-5-2025-08-07")
    assert should_set_litellm_extra_body("openhands/devstral-small-2507")


def test_should_set_litellm_extra_body_for_llm_proxy_base_url():
    """Test that litellm_extra_body is set for models using llm-proxy base URLs."""
    # Any model using llm-proxy.*.all-hands.dev should get metadata
    assert should_set_litellm_extra_body(
        "gpt-4", "https://llm-proxy.app.all-hands.dev/"
    )
    assert should_set_litellm_extra_body(
        "anthropic/claude-3", "https://llm-proxy.app.all-hands.dev/v1"
    )
    assert should_set_litellm_extra_body(
        "openai/gpt-4", "https://llm-proxy.staging.all-hands.dev/"
    )
    assert should_set_litellm_extra_body(
        "custom-model", "https://llm-proxy.dev.all-hands.dev/api"
    )


def test_should_not_set_litellm_extra_body_for_other_models():
    """Test that litellm_extra_body is not set for non-openhands models."""
    assert not should_set_litellm_extra_body("gpt-4")
    assert not should_set_litellm_extra_body("anthropic/claude-3")
    assert not should_set_litellm_extra_body("openai/gpt-4")
    assert not should_set_litellm_extra_body("cerebras/llama3.1-8b")
    assert not should_set_litellm_extra_body("vllm/model")
    assert not should_set_litellm_extra_body("dummy-model")
    assert not should_set_litellm_extra_body("litellm_proxy/gpt-4")


def test_should_not_set_litellm_extra_body_for_other_base_urls():
    """Test that litellm_extra_body is not set for non-OpenHands base URLs."""
    assert not should_set_litellm_extra_body("gpt-4", "https://api.openai.com/")
    assert not should_set_litellm_extra_body("claude-3", "https://api.anthropic.com/v1")
    assert not should_set_litellm_extra_body(
        "model", "https://example.com/llm-proxy.app.all-hands.dev/"
    )
    assert not should_set_litellm_extra_body("model", "https://all-hands.dev/")
    assert not should_set_litellm_extra_body("model", None)


def test_convert_acp_mcp_servers_empty_list():
    """Test converting empty list of MCP servers."""
    result = convert_acp_mcp_servers_to_agent_format([])
    assert result == {}


def test_convert_acp_mcp_servers_with_empty_env():
    """Test converting MCP server with empty env array."""
    servers = [
        McpServerStdio(
            name="test-server",
            command="/usr/bin/node",
            args=["server.js"],
            env=[],
        )
    ]
    result = convert_acp_mcp_servers_to_agent_format(servers)

    assert "test-server" in result
    assert result["test-server"]["command"] == "/usr/bin/node"
    assert result["test-server"]["args"] == ["server.js"]
    assert result["test-server"]["env"] == {}
    assert result["test-server"]["transport"] == "stdio"
    assert "name" not in result["test-server"]


def test_convert_acp_mcp_servers_with_env_variables():
    """Test converting MCP server with env variables."""
    servers = [
        McpServerStdio(
            name="test-server",
            command="/usr/bin/python",
            args=["-m", "server"],
            env=[
                EnvVariable(name="API_KEY", value="secret123"),
                EnvVariable(name="DEBUG", value="true"),
            ],
        )
    ]
    result = convert_acp_mcp_servers_to_agent_format(servers)

    assert "test-server" in result
    assert result["test-server"]["env"] == {
        "API_KEY": "secret123",
        "DEBUG": "true",
    }


def test_convert_acp_mcp_servers_multiple_servers():
    """Test converting multiple MCP servers."""
    servers = [
        McpServerStdio(
            name="server1",
            command="/usr/bin/node",
            args=["server1.js"],
            env=[],
        ),
        McpServerStdio(
            name="server2",
            command="/usr/bin/python",
            args=["-m", "server2"],
            env=[EnvVariable(name="KEY", value="value")],
        ),
    ]
    result = convert_acp_mcp_servers_to_agent_format(servers)

    assert len(result) == 2
    assert "server1" in result
    assert "server2" in result
    assert result["server1"]["env"] == {}
    assert result["server2"]["env"] == {"KEY": "value"}


def test_seeded_instructions_task_only():
    args = Namespace(command=None, task="Do something", file=None)
    assert create_seeded_instructions_from_args(args) == ["Do something"]


def test_seeded_instructions_file_only(tmp_path):
    path = tmp_path / "context.txt"
    path.write_text("hello", encoding="utf-8")

    args = Namespace(command=None, task=None, file=str(path))
    queued = create_seeded_instructions_from_args(args)

    assert isinstance(queued, list)
    assert len(queued) == 1
    assert "File path:" in queued[0]


class TestJsonCallback:
    """Minimal tests for json_callback function core behavior."""

    def test_json_callback_filters_system_events_and_outputs_others(self):
        """Test that SystemPromptEvent is filtered and other events output as JSON."""
        # Test SystemPromptEvent filtering
        system_event = SystemPromptEvent(
            system_prompt=TextContent(text="test prompt"), tools=[], source="agent"
        )

        with patch("builtins.print") as mock_print:
            json_callback(system_event)
            mock_print.assert_not_called()

        # Test non-system event JSON output
        message_event = MessageEvent(
            llm_message=Message(
                role="user", content=[TextContent(text="test message")]
            ),
            source="user",
        )

        with patch("builtins.print") as mock_print:
            json_callback(message_event)

            # Should have two print calls: header and JSON
            assert mock_print.call_count == 2
            mock_print.assert_any_call("--JSON Event--")

            # Verify valid JSON output
            json_output = mock_print.call_args_list[1][0][0]
            parsed_json = json.loads(json_output)
            assert isinstance(parsed_json, dict)

    def test_json_callback_real_message_event_processing(self):
        """Test json_callback with realistic MessageEvent processing."""
        event = MessageEvent(
            llm_message=Message(
                role="user", content=[TextContent(text="Hello, this is a test message")]
            ),
            source="user",
        )

        with patch("builtins.print") as mock_print:
            json_callback(event)

            # Verify the output structure
            assert mock_print.call_count == 2
            mock_print.assert_any_call("--JSON Event--")

            # Get and validate the JSON output
            json_output = mock_print.call_args_list[1][0][0]
            parsed_json = json.loads(json_output)

            # Verify essential fields are present
            assert "llm_message" in parsed_json
            assert "source" in parsed_json
            assert parsed_json["source"] == "user"

            # Check the message content structure
            llm_message = parsed_json["llm_message"]
            assert "content" in llm_message
            content = llm_message["content"]
            assert isinstance(content, list)
            assert len(content) > 0
            assert content[0]["text"] == "Hello, this is a test message"


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        # No events directory at all
        (None, False),
        # Empty events directory
        ([], False),
        # Events without delegate
        (
            [
                {"tool_name": "terminal", "id": "event-1"},
                {"tool_name": "file_editor", "id": "event-2"},
                {"tool_name": "task_tracker", "id": "event-3"},
            ],
            False,
        ),
        # Events with delegate
        (
            [
                {"tool_name": "terminal", "id": "event-1"},
                {"tool_name": "delegate", "id": "event-2"},
                {"tool_name": "file_editor", "id": "event-3"},
            ],
            True,
        ),
    ],
    ids=[
        "no_events_dir",
        "empty_events_dir",
        "events_without_delegate",
        "events_with_delegate",
    ],
)
def test_conversation_has_delegate_tool_events(tmp_path, monkeypatch, setup, expected):
    """Detect DelegateTool usage from conversation events."""
    monkeypatch.setattr(
        "openhands_cli.utils.get_conversations_dir", lambda: str(tmp_path)
    )
    conv_id = "test-conv"

    if setup is not None:
        events_dir = tmp_path / conv_id / "events"
        events_dir.mkdir(parents=True)
        for i, event in enumerate(setup):
            event_file = events_dir / f"event-{i:05d}-abc123.json"
            event_file.write_text(json.dumps(event))

    assert conversation_has_delegate_tool_events(conv_id) is expected


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        # Invalid JSON before a valid delegate event — still detected
        (
            [
                ("event-00000-abc.json", "not valid json"),
                ("event-00001-def.json", json.dumps({"tool_name": "delegate"})),
            ],
            True,
        ),
        # All invalid JSON — returns False
        (
            [
                ("event-00000-abc.json", "not valid json"),
                ("event-00001-def.json", "{broken json"),
            ],
            False,
        ),
    ],
    ids=["invalid_json_with_delegate", "only_invalid_json"],
)
def test_conversation_has_delegate_handles_invalid_json(
    tmp_path, monkeypatch, files, expected
):
    """Gracefully handle invalid JSON event files."""
    monkeypatch.setattr(
        "openhands_cli.utils.get_conversations_dir", lambda: str(tmp_path)
    )
    conv_id = "test-conv-invalid"
    events_dir = tmp_path / conv_id / "events"
    events_dir.mkdir(parents=True)

    for filename, content in files:
        (events_dir / filename).write_text(content)

    assert conversation_has_delegate_tool_events(conv_id) is expected
