"""Tests for utility functions."""

import json
from argparse import Namespace
from unittest.mock import patch

from acp.schema import EnvVariable, StdioMcpServer

from openhands.sdk.event import MessageEvent, SystemPromptEvent
from openhands.sdk.llm import Message, TextContent
from openhands_cli.acp_impl.utils import convert_acp_mcp_servers_to_agent_format
from openhands_cli.utils import (
    create_seeded_instructions_from_args,
    json_callback,
    should_set_litellm_extra_body,
)


def test_should_set_litellm_extra_body_for_openhands():
    """Test that litellm_extra_body is set for openhands models."""
    assert should_set_litellm_extra_body("openhands/claude-sonnet-4-5-20250929")
    assert should_set_litellm_extra_body("openhands/gpt-5-2025-08-07")
    assert should_set_litellm_extra_body("openhands/devstral-small-2507")


def test_should_not_set_litellm_extra_body_for_other_models():
    """Test that litellm_extra_body is not set for non-openhands models."""
    assert not should_set_litellm_extra_body("gpt-4")
    assert not should_set_litellm_extra_body("anthropic/claude-3")
    assert not should_set_litellm_extra_body("openai/gpt-4")
    assert not should_set_litellm_extra_body("cerebras/llama3.1-8b")
    assert not should_set_litellm_extra_body("vllm/model")
    assert not should_set_litellm_extra_body("dummy-model")
    assert not should_set_litellm_extra_body("litellm_proxy/gpt-4")


def test_convert_acp_mcp_servers_empty_list():
    """Test converting empty list of MCP servers."""
    result = convert_acp_mcp_servers_to_agent_format([])
    assert result == {}


def test_convert_acp_mcp_servers_with_empty_env():
    """Test converting MCP server with empty env array."""
    servers = [
        StdioMcpServer(
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
        StdioMcpServer(
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
        StdioMcpServer(
            name="server1",
            command="/usr/bin/node",
            args=["server1.js"],
            env=[],
        ),
        StdioMcpServer(
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
