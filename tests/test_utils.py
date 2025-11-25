"""Tests for utility functions."""

from argparse import Namespace

from acp.schema import EnvVariable, StdioMcpServer

from openhands_cli.acp_impl.utils import convert_acp_mcp_servers_to_agent_format
from openhands_cli.utils import (
    create_seeded_instructions_from_args,
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
    assert result["test-server"]["type"] == "stdio"
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
