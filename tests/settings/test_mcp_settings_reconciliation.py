"""Minimal tests: mcp.json overrides persisted agent MCP servers."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM, Agent
from openhands_cli.locations import AGENT_SETTINGS_PATH, MCP_CONFIG_FILE
from openhands_cli.stores import AgentStore


# ---------------------- tiny helpers ----------------------


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj))


def write_agent(root: Path, agent: Agent) -> None:
    (root / AGENT_SETTINGS_PATH).write_text(
        agent.model_dump_json(context={"expose_secrets": True})
    )


# ---------------------- fixtures ----------------------


@pytest.fixture
def persistence_dir(tmp_path, monkeypatch) -> Path:
    # Create root dir and point AgentStore at it
    root = tmp_path / "openhands"
    root.mkdir()
    # Patch PERSISTENCE_DIR in both modules that use it
    monkeypatch.setattr("openhands_cli.locations.PERSISTENCE_DIR", str(root))
    monkeypatch.setattr("openhands_cli.locations.PERSISTENCE_DIR", str(root))
    return root


@pytest.fixture
def agent_store() -> AgentStore:
    return AgentStore()


# ---------------------- tests ----------------------


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_overrides_persisted_mcp_with_mcp_json_file(
    mock_meta, mock_tools, persistence_dir, agent_store
):
    """If agent has MCP servers, mcp.json must replace them entirely."""
    # Persist an agent that already contains MCP servers
    persisted_agent = Agent(
        llm=LLM(model="gpt-4", api_key=SecretStr("k"), usage_id="svc"),
        tools=[],
        mcp_config={
            "mcpServers": {
                "persistent_server": {"command": "python", "args": ["-m", "old_server"]}
            }
        },
    )
    write_agent(persistence_dir, persisted_agent)

    # Create mcp.json with different servers (this must fully override)
    write_json(
        persistence_dir / MCP_CONFIG_FILE,
        {
            "mcpServers": {
                "file_server": {"command": "uvx", "args": ["mcp-server-fetch"]}
            }
        },
    )

    loaded = agent_store.load()
    assert loaded is not None
    # Expect ONLY the MCP json file's config
    assert "mcpServers" in loaded.mcp_config
    assert "file_server" in loaded.mcp_config["mcpServers"]

    # Check server properties
    file_server = loaded.mcp_config["mcpServers"]["file_server"]
    assert file_server.command == "uvx"
    assert file_server.args == ["mcp-server-fetch"]
    assert file_server.transport == "stdio"


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_when_mcp_file_missing_ignores_persisted_mcp(
    mock_meta, mock_tools, persistence_dir, agent_store
):
    """If mcp.json is absent, loaded agent.mcp_config should be empty
    (persisted MCP ignored)."""
    persisted_agent = Agent(
        llm=LLM(model="gpt-4", api_key=SecretStr("k"), usage_id="svc"),
        tools=[],
        mcp_config={
            "mcpServers": {
                "persistent_server": {"command": "python", "args": ["-m", "old_server"]}
            }
        },
    )
    write_agent(persistence_dir, persisted_agent)

    # No mcp.json created

    loaded = agent_store.load()
    assert loaded is not None
    assert loaded.mcp_config == {}  # persisted MCP is ignored if file is missing


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_mcp_configuration_filters_disabled_servers(
    mock_meta, mock_tools, persistence_dir, agent_store
):
    """Test that load_mcp_configuration filters out disabled servers."""
    # Persist a basic agent first
    persisted_agent = Agent(
        llm=LLM(model="gpt-4", api_key=SecretStr("k"), usage_id="svc"),
        tools=[],
    )
    write_agent(persistence_dir, persisted_agent)

    # Create mcp.json with enabled and disabled servers
    write_json(
        persistence_dir / MCP_CONFIG_FILE,
        {
            "mcpServers": {
                "enabled_server": {
                    "command": "uvx",
                    "args": ["mcp-server-fetch"],
                    "enabled": True,
                },
                "disabled_server": {
                    "command": "python",
                    "args": ["-m", "disabled"],
                    "enabled": False,
                },
                "default_enabled_server": {
                    "command": "node",
                    "args": ["server.js"],
                    # No 'enabled' field - should default to True
                },
            }
        },
    )

    loaded = agent_store.load()
    assert loaded is not None

    # Should only load enabled servers (enabled_server and default_enabled_server)
    assert "enabled_server" in loaded.mcp_config["mcpServers"]
    assert "default_enabled_server" in loaded.mcp_config["mcpServers"]
    assert "disabled_server" not in loaded.mcp_config["mcpServers"]

    # Verify the loaded servers have correct properties
    assert loaded.mcp_config["mcpServers"]["enabled_server"].command == "uvx"
    default_enabled = loaded.mcp_config["mcpServers"]["default_enabled_server"]
    assert default_enabled.command == "node"


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_mcp_configuration_all_disabled(
    mock_meta, mock_tools, persistence_dir, agent_store
):
    """Test load_mcp_configuration returns empty dict when all servers disabled."""
    # Persist a basic agent first
    persisted_agent = Agent(
        llm=LLM(model="gpt-4", api_key=SecretStr("k"), usage_id="svc"),
        tools=[],
    )
    write_agent(persistence_dir, persisted_agent)

    # Create mcp.json with all disabled servers
    write_json(
        persistence_dir / MCP_CONFIG_FILE,
        {
            "mcpServers": {
                "disabled_server1": {
                    "command": "python",
                    "args": ["-m", "server1"],
                    "enabled": False,
                },
                "disabled_server2": {
                    "command": "python",
                    "args": ["-m", "server2"],
                    "enabled": False,
                },
            }
        },
    )

    loaded = agent_store.load()
    assert loaded is not None
    # When all servers are disabled, mcp_config becomes empty dict
    assert loaded.mcp_config == {}
