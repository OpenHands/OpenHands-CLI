"""Unit tests for MCP configuration management."""

import json
import tempfile
from pathlib import Path

import pytest

from openhands_cli.mcp.mcp_utils import (
    MCPConfigurationError,
    _load_config,
    _parse_env_vars,
    _parse_headers,
    add_server,
    get_server,
    list_servers,
    remove_server,
    server_exists,
)


class TestMCPFunctions:
    """Test cases for MCP management functions."""

    def test_load_config_nonexistent_file(self):
        """Test loading config when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "nonexistent.json"
            config = _load_config(str(config_path))
            assert config == {"mcpServers": {}}

    def test_load_config_valid_file(self):
        """Test loading config from valid JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"
            test_config = {
                "mcpServers": {"test_server": {"command": "test", "transport": "stdio"}}
            }
            config_path.write_text(json.dumps(test_config))

            config = _load_config(str(config_path))
            assert config == test_config

    def test_load_config_missing_mcp_servers_key(self):
        """Test loading config that's missing mcpServers key."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"
            test_config = {"other_key": "value"}
            config_path.write_text(json.dumps(test_config))

            config = _load_config(str(config_path))
            assert "mcpServers" in config
            assert config["mcpServers"] == {}

    def test_load_config_invalid_json(self):
        """Test loading config with invalid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"
            config_path.write_text('{"invalid": json}')

            with pytest.raises(MCPConfigurationError, match="Invalid JSON"):
                _load_config(str(config_path))

    def test_parse_headers_valid(self):
        """Test parsing valid header strings."""
        headers = ["Authorization: Bearer token", "Content-Type: application/json"]
        result = _parse_headers(headers)
        expected = {
            "Authorization": "Bearer token",
            "Content-Type": "application/json",
        }
        assert result == expected

    def test_parse_headers_empty(self):
        """Test parsing empty header list."""
        assert _parse_headers(None) == {}
        assert _parse_headers([]) == {}

    def test_parse_headers_invalid_format(self):
        """Test parsing headers with invalid format."""
        with pytest.raises(MCPConfigurationError, match="Invalid header format"):
            _parse_headers(["invalid-header"])

    def test_parse_env_vars_valid(self):
        """Test parsing valid environment variable strings."""
        env_vars = ["API_KEY=secret", "DEBUG=true"]
        result = _parse_env_vars(env_vars)
        expected = {"API_KEY": "secret", "DEBUG": "true"}
        assert result == expected

    def test_parse_env_vars_empty(self):
        """Test parsing empty env var list."""
        assert _parse_env_vars(None) == {}
        assert _parse_env_vars([]) == {}

    def test_parse_env_vars_invalid_format(self):
        """Test parsing env vars with invalid format."""
        with pytest.raises(MCPConfigurationError, match="Invalid environment variable"):
            _parse_env_vars(["INVALID_ENV_VAR"])

    def test_add_server_http(self):
        """Test adding HTTP MCP server."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            add_server(
                name="test_http",
                transport="http",
                target="https://api.example.com/mcp",
                headers=["Authorization: Bearer token"],
                config_path=str(config_path),
            )

            config = _load_config(str(config_path))
            server = config["mcpServers"]["test_http"]
            assert server["transport"] == "http"
            assert server["url"] == "https://api.example.com/mcp"
            assert server["headers"]["Authorization"] == "Bearer token"

    def test_add_server_http_with_oauth(self):
        """Test adding HTTP MCP server with OAuth authentication."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            add_server(
                name="test_oauth",
                transport="http",
                target="https://mcp.notion.com/mcp",
                auth="oauth",
                config_path=str(config_path),
            )

            config = _load_config(str(config_path))
            server = config["mcpServers"]["test_oauth"]
            assert server["transport"] == "http"
            assert server["url"] == "https://mcp.notion.com/mcp"
            assert server["auth"] == "oauth"

    def test_add_server_sse(self):
        """Test adding SSE MCP server."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            add_server(
                name="test_sse",
                transport="sse",
                target="https://api.example.com/sse",
                headers=["X-API-Key: secret"],
                config_path=str(config_path),
            )

            config = _load_config(str(config_path))
            server = config["mcpServers"]["test_sse"]
            assert server["transport"] == "sse"
            assert server["url"] == "https://api.example.com/sse"
            assert server["headers"]["X-API-Key"] == "secret"

    def test_add_server_stdio(self):
        """Test adding stdio MCP server."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            add_server(
                name="test_stdio",
                transport="stdio",
                target="python",
                args=["-m", "test_server"],
                env_vars=["API_KEY=secret", "DEBUG=true"],
                config_path=str(config_path),
            )

            config = _load_config(str(config_path))
            server = config["mcpServers"]["test_stdio"]
            assert server["transport"] == "stdio"
            assert server["command"] == "python"
            assert server["args"] == ["-m", "test_server"]
            assert server["env"]["API_KEY"] == "secret"
            assert server["env"]["DEBUG"] == "true"

    def test_add_server_already_exists(self):
        """Test adding server that already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            # Add server first time
            add_server(
                "test", "http", "https://example.com", config_path=str(config_path)
            )

            # Try to add same server again
            with pytest.raises(MCPConfigurationError, match="already exists"):
                add_server(
                    "test", "http", "https://example.com", config_path=str(config_path)
                )

    def test_add_server_invalid_transport(self):
        """Test adding server with invalid transport."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            with pytest.raises(MCPConfigurationError, match="Invalid transport type"):
                add_server("test", "invalid", "target", config_path=str(config_path))

    def test_remove_server_success(self):
        """Test removing existing server."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            # Add server first
            add_server(
                "test", "http", "https://example.com", config_path=str(config_path)
            )

            # Remove server
            remove_server("test", config_path=str(config_path))

            config = _load_config(str(config_path))
            assert "test" not in config["mcpServers"]

    def test_remove_server_not_found(self):
        """Test removing non-existent server."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            with pytest.raises(MCPConfigurationError, match="not found"):
                remove_server("nonexistent", config_path=str(config_path))

    def test_list_servers_empty(self):
        """Test listing servers when none exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            servers = list_servers(config_path=str(config_path))
            assert servers == {}

    def test_list_servers_with_servers(self):
        """Test listing servers when some exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            # Add multiple servers
            add_server(
                "http_server",
                "http",
                "https://example.com",
                config_path=str(config_path),
            )
            add_server(
                "stdio_server",
                "stdio",
                "python",
                args=["-m", "server"],
                config_path=str(config_path),
            )

            servers = list_servers(config_path=str(config_path))
            assert len(servers) == 2
            assert "http_server" in servers
            assert "stdio_server" in servers

    def test_get_server_success(self):
        """Test getting existing server configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            # Add server
            add_server(
                "test", "http", "https://example.com", config_path=str(config_path)
            )

            # Get server
            config = get_server("test", config_path=str(config_path))
            assert config["transport"] == "http"
            assert config["url"] == "https://example.com"

    def test_get_server_not_found(self):
        """Test getting non-existent server."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            with pytest.raises(MCPConfigurationError, match="not found"):
                get_server("nonexistent", config_path=str(config_path))

    def test_server_exists_true(self):
        """Test server_exists returns True for existing server."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            add_server(
                "test", "http", "https://example.com", config_path=str(config_path)
            )
            assert server_exists("test", config_path=str(config_path)) is True

    def test_server_exists_false(self):
        """Test server_exists returns False for non-existent server."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            assert server_exists("nonexistent", config_path=str(config_path)) is False

    def test_server_exists_with_invalid_config(self):
        """Test server_exists handles invalid config gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"
            config_path.write_text('{"invalid": json}')

            assert server_exists("test", config_path=str(config_path)) is False

    def test_add_server_validates_configuration(self):
        """Test that add_server validates the configuration after saving."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            # Add a valid server - should not raise validation error
            add_server(
                name="test_server",
                transport="http",
                target="https://api.example.com",
                config_path=str(config_path),
            )

            # Verify the server was added and config is valid
            assert server_exists("test_server", config_path=str(config_path))

            # The configuration should be loadable by MCPConfig
            from fastmcp.mcp_config import MCPConfig

            mcp_config = MCPConfig.from_file(config_path)
            assert "test_server" in mcp_config.to_dict()["mcpServers"]

    def test_add_oauth_server_validates_configuration(self):
        """Test that OAuth server configuration is valid."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"

            # Add an OAuth server - should not raise validation error
            add_server(
                name="notion_server",
                transport="http",
                target="https://mcp.notion.com/mcp",
                auth="oauth",
                config_path=str(config_path),
            )

            # Verify the server was added and config is valid
            assert server_exists("notion_server", config_path=str(config_path))

            # The configuration should be loadable by MCPConfig
            from fastmcp.mcp_config import MCPConfig

            mcp_config = MCPConfig.from_file(config_path)
            servers = mcp_config.to_dict()["mcpServers"]
            assert "notion_server" in servers
            assert servers["notion_server"]["auth"] == "oauth"
