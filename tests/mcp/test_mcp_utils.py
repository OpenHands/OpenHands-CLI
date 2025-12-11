"""Unit tests for MCP configuration management."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer

from openhands_cli.mcp.mcp_utils import (
    MCPConfigurationError,
    _parse_env_vars,
    _parse_headers,
    add_server,
    get_config_status,
    get_server,
    list_servers,
    load_mcp_config,
    remove_server,
    server_exists,
)


@pytest.fixture
def temp_config_path():
    """Fixture that provides a temporary config path and patches PERSISTENCE_DIR."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "mcp.json"
        # Patch PERSISTENCE_DIR so that _get_mcp_config_path() returns our temp path
        with patch("openhands_cli.locations.PERSISTENCE_DIR", str(temp_dir)):
            yield config_path


class TestMCPFunctions:
    """Test cases for MCP management functions."""

    def test_load_config_nonexistent_file(self, temp_config_path):
        """Test loading config when file doesn't exist."""
        config = load_mcp_config()
        assert config.to_dict() == {"mcpServers": {}}

    def test_load_config_valid_file(self, temp_config_path):
        """Test loading config from valid JSON file."""
        test_config = {
            "mcpServers": {"test_server": {"command": "test", "transport": "stdio"}}
        }
        temp_config_path.write_text(json.dumps(test_config))

        config = load_mcp_config()
        # Check that the server was loaded correctly
        servers_dict = config.to_dict()["mcpServers"]
        assert "test_server" in servers_dict
        assert servers_dict["test_server"]["command"] == "test"
        assert servers_dict["test_server"]["transport"] == "stdio"

    def test_load_config_missing_mcp_servers_key(self, temp_config_path):
        """Test loading config that's missing mcpServers key."""
        test_config = {"other_key": "value"}
        temp_config_path.write_text(json.dumps(test_config))

        config = load_mcp_config()
        config_dict = config.to_dict()
        assert "mcpServers" in config_dict
        assert config_dict["mcpServers"] == {}

    def test_load_config_invalid_json(self, temp_config_path):
        """Test loading config with invalid JSON."""
        temp_config_path.write_text("invalid json content")

        with pytest.raises(MCPConfigurationError):
            load_mcp_config()

    def test_add_server_stdio(self, temp_config_path):
        """Test adding a stdio MCP server."""
        add_server(
            "test",
            "stdio",
            "python",
            args=["-m", "test"],
            env_vars=["VAR1=value1", "VAR2=value2"],
        )

        # Verify server was added
        config = load_mcp_config()
        servers_dict = config.to_dict()["mcpServers"]
        assert "test" in servers_dict
        server = servers_dict["test"]
        assert server["command"] == "python"
        assert server["args"] == ["-m", "test"]
        assert server["env"]["VAR1"] == "value1"
        assert server["env"]["VAR2"] == "value2"

    def test_add_server_http(self, temp_config_path):
        """Test adding an HTTP MCP server."""
        add_server(
            "test",
            "http",
            "https://example.com",
            headers=["Authorization: Bearer token", "Content-Type: application/json"],
        )

        # Verify server was added
        config = load_mcp_config()
        servers_dict = config.to_dict()["mcpServers"]
        assert "test" in servers_dict
        server = servers_dict["test"]
        assert server["url"] == "https://example.com"
        assert server["headers"]["Authorization"] == "Bearer token"
        assert server["headers"]["Content-Type"] == "application/json"

    def test_add_server_oauth(self, temp_config_path):
        """Test adding an OAuth MCP server."""
        add_server(
            "test",
            "http",
            "https://example.com",
            auth="oauth",
        )

        # Verify server was added
        config = load_mcp_config()
        servers_dict = config.to_dict()["mcpServers"]
        assert "test" in servers_dict
        server = servers_dict["test"]
        assert server["url"] == "https://example.com"
        assert server["auth"] == "oauth"

    def test_add_server_duplicate(self, temp_config_path):
        """Test adding a server with duplicate name."""
        add_server("test", "http", "https://example.com")

        with pytest.raises(MCPConfigurationError, match="already exists"):
            add_server("test", "http", "https://example.com")

    def test_add_server_invalid_transport(self, temp_config_path):
        """Test adding server with invalid transport."""
        with pytest.raises(MCPConfigurationError, match="Invalid transport type"):
            add_server("test", "invalid", "target")

    def test_remove_server_success(self, temp_config_path):
        """Test removing an existing server."""
        add_server("test", "http", "https://example.com")
        remove_server("test")

        # Verify server was removed
        config = load_mcp_config()
        servers_dict = config.to_dict()["mcpServers"]
        assert "test" not in servers_dict

    def test_remove_server_nonexistent(self, temp_config_path):
        """Test removing a non-existent server."""
        with pytest.raises(MCPConfigurationError, match="not found"):
            remove_server("nonexistent")

    def test_list_servers_empty(self, temp_config_path):
        """Test listing servers when none exist."""
        servers = list_servers()
        assert servers == {}

    def test_list_servers_with_data(self, temp_config_path):
        """Test listing servers with existing data."""
        add_server(
            "test1",
            "stdio",
            "python",
        )
        add_server(
            "test2",
            "http",
            "https://example.com",
        )

        servers = list_servers()
        assert len(servers) == 2
        assert "test1" in servers
        assert "test2" in servers
        # Check that we get FastMCP server objects
        assert isinstance(servers["test1"], StdioMCPServer)
        assert isinstance(servers["test2"], RemoteMCPServer)

    def test_get_server_success(self, temp_config_path):
        """Test getting an existing server."""
        add_server("test", "http", "https://example.com")
        server = get_server("test")

        # Check that we get a FastMCP server object
        assert isinstance(server, RemoteMCPServer)
        assert server.url == "https://example.com"
        assert server.transport == "http"

    def test_get_server_nonexistent(self, temp_config_path):
        """Test getting a non-existent server."""
        with pytest.raises(MCPConfigurationError, match="not found"):
            get_server("nonexistent")

    def test_server_exists_true(self, temp_config_path):
        """Test server_exists returns True for existing server."""
        add_server("test", "http", "https://example.com")
        assert server_exists("test") is True

    def test_server_exists_false(self, temp_config_path):
        """Test server_exists returns False for non-existent server."""
        assert server_exists("nonexistent") is False

    def test_server_exists_invalid_config(self, temp_config_path):
        """Test server_exists returns False when config is invalid."""
        temp_config_path.write_text("invalid json")
        assert server_exists("test") is False

    def test_add_server_stdio_with_env_vars(self, temp_config_path):
        """Test adding stdio server with environment variables."""
        add_server(
            "test_server",
            "stdio",
            "python",
            args=["-m", "test_module"],
            env_vars=["API_KEY=secret123", "DEBUG=true"],
        )
        assert server_exists("test_server")

    def test_add_server_notion_oauth(self, temp_config_path):
        """Test adding Notion server with OAuth."""
        add_server(
            "notion_server",
            "http",
            "https://api.notion.com",
            auth="oauth",
        )
        assert server_exists("notion_server")

    def test_get_config_status_nonexistent(self, temp_config_path):
        """Test get_config_status when config file doesn't exist."""
        status = get_config_status()
        assert status["exists"] is False
        assert status["valid"] is False
        assert status["servers"] == {}
        assert "not found" in status["message"]

    def test_get_config_status_valid(self, temp_config_path):
        """Test get_config_status with valid config file."""
        add_server("test_server", "http", "https://example.com")

        status = get_config_status()
        assert status["exists"] is True
        assert status["valid"] is True
        assert "test_server" in status["servers"]
        assert "1 server(s)" in status["message"]

    def test_get_config_status_invalid(self, temp_config_path):
        """Test get_config_status with invalid config file."""
        temp_config_path.write_text("invalid json content")

        status = get_config_status()
        assert status["exists"] is True
        assert status["valid"] is False
        assert status["servers"] == {}
        assert "Invalid" in status["message"]


class TestParseHelpers:
    """Test cases for parsing helper functions."""

    def test_parse_headers_valid(self):
        """Test parsing valid headers."""
        headers = ["Authorization: Bearer token", "Content-Type: application/json"]
        parsed = _parse_headers(headers)
        assert parsed == {
            "Authorization": "Bearer token",
            "Content-Type": "application/json",
        }

    def test_parse_headers_empty(self):
        """Test parsing empty headers."""
        assert _parse_headers(None) == {}
        assert _parse_headers([]) == {}

    def test_parse_headers_invalid_format(self):
        """Test parsing headers with invalid format."""
        headers = ["invalid_header_format"]
        with pytest.raises(MCPConfigurationError, match="Invalid header format"):
            _parse_headers(headers)

    def test_parse_env_vars_valid(self):
        """Test parsing valid environment variables."""
        env_vars = ["VAR1=value1", "VAR2=value2"]
        parsed = _parse_env_vars(env_vars)
        assert parsed == {"VAR1": "value1", "VAR2": "value2"}

    def test_parse_env_vars_empty(self):
        """Test parsing empty environment variables."""
        assert _parse_env_vars(None) == {}
        assert _parse_env_vars([]) == {}

    def test_parse_env_vars_invalid_format(self):
        """Test parsing environment variables with invalid format."""
        env_vars = ["invalid_env_format"]
        with pytest.raises(
            MCPConfigurationError, match="Invalid environment variable format"
        ):
            _parse_env_vars(env_vars)
