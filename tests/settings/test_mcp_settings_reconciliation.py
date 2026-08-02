"""Minimal tests: mcp.json overrides persisted agent MCP servers."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from openhands_cli.locations import AGENT_SETTINGS_PATH, MCP_CONFIG_FILE
from openhands_cli.stores import AgentStore
from tests.conftest import MockLocations, save_test_agent


# ---------------------- tiny helpers ----------------------


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj))


# ---------------------- fixtures ----------------------


@pytest.fixture
def persistence_dir(mock_locations: MockLocations) -> Path:
    """Return the persistence directory from mock_locations."""
    return mock_locations.persistence_dir


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
    save_test_agent(
        persistence_dir,
        mcp_config={
            "persistent_server": {"command": "python", "args": ["-m", "old_server"]}
        },
    )

    # Create mcp.json with different servers (this must fully override)
    write_json(
        persistence_dir / MCP_CONFIG_FILE,
        {
            "mcpServers": {
                "file_server": {"command": "uvx", "args": ["mcp-server-fetch"]}
            }
        },
    )

    loaded = agent_store.load_or_create()
    assert loaded is not None
    # Expect ONLY the MCP json file's config
    assert "file_server" in loaded.mcp_config

    # Check server properties
    file_server = loaded.mcp_config["file_server"]
    assert file_server.command == "uvx"
    assert file_server.args == ["mcp-server-fetch"]
    assert file_server.transport == "stdio"


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_legacy_persisted_mcp_wrapper(
    mock_meta, mock_tools, persistence_dir, agent_store
):
    """A persisted agent with the pre-1.32 {"mcpServers": ...} wrapper loads.

    openhands-sdk >= 1.32 expects mcp_config as dict[str, MCPServer]. Agents
    saved by older CLI versions used the wrapped format, which is coerced to
    the flat format at load. mcp.json remains the single source of truth for
    MCP servers (applied by load_or_create).
    """
    agent = save_test_agent(persistence_dir, mcp_config={})
    data = json.loads(agent.model_dump_json(context={"expose_secrets": True}))
    data["mcp_config"] = {
        "mcpServers": {
            "legacy_server": {"command": "python", "args": ["-m", "old_server"]}
        }
    }
    (persistence_dir / AGENT_SETTINGS_PATH).write_text(json.dumps(data))

    # load_from_disk must NOT report the legacy wrapper as corrupted; the
    # persisted MCP config is coerced to the flat format.
    loaded = agent_store.load_from_disk()
    assert loaded is not None
    assert set(loaded.mcp_config) == {"legacy_server"}
    assert loaded.mcp_config["legacy_server"].command == "python"
    assert loaded.llm.model == "openai/gpt-4o-mini"

    # load_or_create applies runtime config (mcp.json), but must NOT report
    # the legacy agent file as corrupted.
    loaded_or_created = agent_store.load_or_create()
    assert loaded_or_created is not None


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_persisted_mcp_with_fastmcp_string_auth(
    mock_meta, mock_tools, persistence_dir, agent_store
):
    """Persisted fastmcp-style string auth is coerced to an SDK credential.

    fastmcp's RemoteMCPServer accepts ``auth`` as a plain string ("oauth" or a
    bearer token); the SDK models auth as a discriminated credential union.
    """
    agent = save_test_agent(persistence_dir, mcp_config={})
    data = json.loads(agent.model_dump_json(context={"expose_secrets": True}))
    data["mcp_config"] = {
        "mcpServers": {
            "oauth_server": {"url": "https://mcp.example.com", "auth": "oauth"},
            "token_server": {"url": "https://api.example.com", "auth": "tok123"},
        }
    }
    (persistence_dir / AGENT_SETTINGS_PATH).write_text(json.dumps(data))

    loaded = agent_store.load_from_disk()
    assert loaded is not None
    assert loaded.mcp_config["oauth_server"].auth.strategy == "oauth2"
    token_auth = loaded.mcp_config["token_server"].auth
    assert token_auth.strategy == "bearer"
    assert token_auth.value.get_secret_value() == "tok123"


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_uncoercible_persisted_mcp_is_dropped(
    mock_meta, mock_tools, persistence_dir, agent_store
):
    """An uncoercible persisted mcp_config is dropped, not reported corrupted."""
    agent = save_test_agent(persistence_dir, mcp_config={})
    data = json.loads(agent.model_dump_json(context={"expose_secrets": True}))
    data["mcp_config"] = {"broken_server": {"transport": "stdio"}}  # no command
    (persistence_dir / AGENT_SETTINGS_PATH).write_text(json.dumps(data))

    loaded = agent_store.load_from_disk()
    assert loaded is not None
    assert loaded.mcp_config == {}
    assert loaded.llm.model == "openai/gpt-4o-mini"


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_non_mcp_validation_error_reports_corrupted(
    mock_meta, mock_tools, persistence_dir, agent_store
):
    """A schema error unrelated to mcp_config is still reported as corrupted.

    The persisted MCP value is dropped unconditionally at load, but other
    broken fields (e.g. tools) must still surface as a corrupted file.
    """
    agent = save_test_agent(persistence_dir, mcp_config={})
    data = json.loads(agent.model_dump_json(context={"expose_secrets": True}))
    data["tools"] = "not-a-list"  # invalid: tools must be a list
    (persistence_dir / AGENT_SETTINGS_PATH).write_text(json.dumps(data))

    loaded = agent_store.load_from_disk()
    assert loaded is None


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_when_mcp_file_missing_ignores_persisted_mcp(
    mock_meta, mock_tools, persistence_dir, agent_store
):
    """If mcp.json is absent, loaded agent.mcp_config should be empty
    (persisted MCP ignored)."""
    save_test_agent(
        persistence_dir,
        mcp_config={
            "persistent_server": {"command": "python", "args": ["-m", "old_server"]}
        },
    )

    # No mcp.json created

    loaded = agent_store.load_or_create()
    assert loaded is not None
    assert loaded.mcp_config == {}  # persisted MCP is ignored if file is missing


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_mcp_configuration_filters_disabled_servers(
    mock_meta, mock_tools, persisted_agent, persistence_dir, agent_store
):
    """Test that load_mcp_configuration filters out disabled servers."""
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

    loaded = agent_store.load_or_create()
    assert loaded is not None

    # Should only load enabled servers (enabled_server and default_enabled_server)
    assert "enabled_server" in loaded.mcp_config
    assert "default_enabled_server" in loaded.mcp_config
    assert "disabled_server" not in loaded.mcp_config

    # Verify the loaded servers have correct properties
    assert loaded.mcp_config["enabled_server"].command == "uvx"
    default_enabled = loaded.mcp_config["default_enabled_server"]
    assert default_enabled.command == "node"


@patch("openhands_cli.stores.agent_store.get_default_cli_tools", return_value=[])
@patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
def test_load_mcp_configuration_all_disabled(
    mock_meta, mock_tools, persisted_agent, persistence_dir, agent_store
):
    """Test load_mcp_configuration returns empty dict when all servers disabled."""
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

    loaded = agent_store.load_or_create()
    assert loaded is not None
    # When all servers are disabled, mcp_config becomes empty dict
    assert loaded.mcp_config == {}
