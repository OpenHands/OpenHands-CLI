"""Unit tests for MCP command handlers."""

import argparse
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer

from openhands_cli.mcp.mcp_commands import (
    handle_mcp_add,
    handle_mcp_command,
    handle_mcp_get,
    handle_mcp_list,
    handle_mcp_remove,
)
from openhands_cli.mcp.mcp_display_utils import mask_sensitive_value


@pytest.fixture
def temp_config_path():
    """Fixture that provides a temporary config path and patches PERSISTENCE_DIR."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "mcp.json"
        # Patch PERSISTENCE_DIR so that _get_mcp_config_path() returns our temp path
        with patch("openhands_cli.locations.PERSISTENCE_DIR", str(temp_dir)):
            yield config_path


class TestMCPCommands:
    """Test cases for MCP command handlers."""

    def test_handle_mcp_add_http_success(self):
        """Test successful HTTP server addition."""
        with tempfile.TemporaryDirectory():
            args = argparse.Namespace(
                name="test_http",
                transport="http",
                target="https://api.example.com",
                args=None,
                header=["Authorization: Bearer token"],
                env=None,
                auth=None,
            )

            with patch("openhands_cli.mcp.mcp_commands.add_server") as mock_add_server:
                with patch("openhands_cli.mcp.mcp_commands.console.print"):
                    handle_mcp_add(args)

                    mock_add_server.assert_called_once_with(
                        name="test_http",
                        transport="http",
                        target="https://api.example.com",
                        args=None,
                        headers=["Authorization: Bearer token"],
                        env_vars=None,
                        auth=None,
                    )

    def test_handle_mcp_add_stdio_success(self):
        """Test successful stdio server addition."""
        args = argparse.Namespace(
            name="test_stdio",
            transport="stdio",
            target="python",
            args=["-m", "server"],
            header=None,
            env=["API_KEY=secret"],
            auth=None,
        )

        with patch("openhands_cli.mcp.mcp_commands.add_server") as mock_add_server:
            with patch("openhands_cli.mcp.mcp_commands.console.print"):
                handle_mcp_add(args)

                mock_add_server.assert_called_once_with(
                    name="test_stdio",
                    transport="stdio",
                    target="python",
                    args=["-m", "server"],
                    headers=None,
                    env_vars=["API_KEY=secret"],
                    auth=None,
                )

    def test_handle_mcp_add_oauth_success(self):
        """Test successful OAuth server addition."""
        with tempfile.TemporaryDirectory():
            args = argparse.Namespace(
                name="notion_server",
                transport="http",
                target="https://mcp.notion.com/mcp",
                args=None,
                header=None,
                env=None,
                auth="oauth",
            )

            with patch("openhands_cli.mcp.mcp_commands.add_server") as mock_add_server:
                with patch("openhands_cli.mcp.mcp_commands.console.print"):
                    handle_mcp_add(args)

                    mock_add_server.assert_called_once_with(
                        name="notion_server",
                        transport="http",
                        target="https://mcp.notion.com/mcp",
                        args=None,
                        headers=None,
                        env_vars=None,
                        auth="oauth",
                    )

    def test_handle_mcp_add_error(self):
        """Test MCP add command with error."""
        args = argparse.Namespace(
            name="test",
            transport="http",
            target="https://example.com",
            args=None,
            header=None,
            env=None,
            auth=None,
        )

        with patch("openhands_cli.mcp.mcp_commands.add_server") as mock_add_server:
            from openhands_cli.mcp.mcp_utils import MCPConfigurationError

            mock_add_server.side_effect = MCPConfigurationError("Test error")

            with patch("openhands_cli.mcp.mcp_commands.console.print") as mock_print:
                with pytest.raises(SystemExit):
                    handle_mcp_add(args)

                # Should print error message
                mock_print.assert_called_once()
                call_args = str(mock_print.call_args)
                assert "Error" in call_args

    def test_handle_mcp_remove_success(self):
        """Test successful server removal."""
        args = argparse.Namespace(name="test_server")

        with patch(
            "openhands_cli.mcp.mcp_commands.remove_server"
        ) as mock_remove_server:
            with patch("openhands_cli.mcp.mcp_commands.console.print"):
                handle_mcp_remove(args)

                mock_remove_server.assert_called_once_with("test_server")

    def test_handle_mcp_remove_error(self):
        """Test MCP remove command with error."""
        args = argparse.Namespace(name="nonexistent")

        with patch(
            "openhands_cli.mcp.mcp_commands.remove_server"
        ) as mock_remove_server:
            from openhands_cli.mcp.mcp_utils import MCPConfigurationError

            mock_remove_server.side_effect = MCPConfigurationError("Server not found")

            with patch("openhands_cli.mcp.mcp_commands.console.print"):
                with pytest.raises(SystemExit):
                    handle_mcp_remove(args)

    def test_handle_mcp_list_empty(self):
        """Test listing when no servers exist."""
        args = argparse.Namespace()

        with patch("openhands_cli.mcp.mcp_commands.list_servers") as mock_list_servers:
            mock_list_servers.return_value = {}

            with patch("openhands_cli.mcp.mcp_commands.console.print") as mock_print:
                handle_mcp_list(args)

                # Should print "no servers" message
                call_args_list = [str(call) for call in mock_print.call_args_list]
                content = " ".join(call_args_list)
                assert "No MCP servers configured" in content

    def test_handle_mcp_list_with_servers(self):
        """Test listing when servers exist."""
        args = argparse.Namespace()

        # Create FastMCP server objects instead of dicts
        test_servers = {
            "http_server": RemoteMCPServer(
                transport="http",
                url="https://api.example.com",
                headers={"Authorization": "Bearer token"},
            ),
            "stdio_server": StdioMCPServer(
                transport="stdio",
                command="python",
                args=["-m", "server"],
                env={"API_KEY": "secret"},
            ),
        }

        with patch("openhands_cli.mcp.mcp_commands.list_servers") as mock_list_servers:
            mock_list_servers.return_value = test_servers

            with patch("openhands_cli.mcp.mcp_commands.console.print") as mock_print:
                handle_mcp_list(args)

                # Should print server details
                call_args_list = [str(call) for call in mock_print.call_args_list]
                content = " ".join(call_args_list)
                assert "http_server" in content
                assert "stdio_server" in content
                assert "Configured MCP servers (2)" in content

    def test_handle_mcp_get_success(self):
        """Test getting server details successfully."""
        args = argparse.Namespace(name="test_server")

        # Create FastMCP server object instead of dict
        test_server = RemoteMCPServer(
            transport="http",
            url="https://api.example.com",
            headers={"Authorization": "Bearer token"},
        )

        with patch("openhands_cli.mcp.mcp_commands.get_server") as mock_get_server:
            mock_get_server.return_value = test_server

            with patch("openhands_cli.mcp.mcp_commands.console.print") as mock_print:
                handle_mcp_get(args)

                mock_get_server.assert_called_once_with("test_server")
                # Should print server details
                call_args_list = [str(call) for call in mock_print.call_args_list]
                content = " ".join(call_args_list)
                assert "test_server" in content

    def test_handle_mcp_get_error(self):
        """Test getting non-existent server."""
        args = argparse.Namespace(name="nonexistent")

        with patch("openhands_cli.mcp.mcp_commands.get_server") as mock_get_server:
            from openhands_cli.mcp.mcp_utils import MCPConfigurationError

            mock_get_server.side_effect = MCPConfigurationError("Server not found")

            with patch("openhands_cli.mcp.mcp_commands.console.print"):
                with pytest.raises(SystemExit):
                    handle_mcp_get(args)

    def test_mask_sensitive_value_sensitive_keys(self):
        """Test masking of sensitive values."""
        # Test various sensitive key patterns
        sensitive_cases = [
            ("authorization", "Bearer secret123", "Bear********t123"),
            ("api_key", "sk-1234567890", "sk-1*****7890"),
            ("token", "abc123", "******"),  # Short value
            ("password", "mypassword", "mypa**word"),
            ("SECRET", "topsecret", "tops*cret"),
        ]

        for key, value, expected in sensitive_cases:
            result = mask_sensitive_value(key, value)
            assert result == expected

    def test_mask_sensitive_value_non_sensitive(self):
        """Test that non-sensitive values are not masked."""
        non_sensitive_cases = [
            ("url", "https://api.example.com"),
            ("command", "python"),
            ("transport", "http"),
            ("name", "test_server"),
        ]

        for key, value in non_sensitive_cases:
            result = mask_sensitive_value(key, value)
            assert result == value

    def test_handle_mcp_command_routing(self):
        """Test that handle_mcp_command routes to correct handlers."""
        test_cases = [
            ("add", "handle_mcp_add"),
            ("remove", "handle_mcp_remove"),
            ("list", "handle_mcp_list"),
            ("get", "handle_mcp_get"),
        ]

        for command, handler_name in test_cases:
            args = argparse.Namespace(mcp_command=command)

            with patch(
                f"openhands_cli.mcp.mcp_commands.{handler_name}"
            ) as mock_handler:
                handle_mcp_command(args)
                mock_handler.assert_called_once_with(args)

    def test_handle_mcp_command_unknown(self):
        """Test handling unknown MCP command."""
        args = argparse.Namespace(mcp_command="unknown")

        with patch("openhands_cli.mcp.mcp_commands.console.print") as mock_print:
            with pytest.raises(SystemExit):
                handle_mcp_command(args)

            # Should print error message
            call_args = str(mock_print.call_args)
            assert "Unknown MCP command" in call_args


class TestMCPCommandsIntegration:
    """Integration tests for MCP commands with real functions."""

    def test_full_workflow_integration(self, temp_config_path):
        """Test complete add -> list -> get -> remove workflow."""
        # Import the real functions for the actual calls
        from openhands_cli.mcp.mcp_utils import (
            add_server,
            get_server,
            list_servers,
            remove_server,
            server_exists,
        )

        # Patch all MCP functions to use the real functions (no config_path needed)
        with (
            patch("openhands_cli.mcp.mcp_commands.add_server", side_effect=add_server),
            patch(
                "openhands_cli.mcp.mcp_commands.list_servers", side_effect=list_servers
            ),
            patch("openhands_cli.mcp.mcp_commands.get_server", side_effect=get_server),
            patch(
                "openhands_cli.mcp.mcp_commands.remove_server",
                side_effect=remove_server,
            ),
        ):
            with patch("openhands_cli.mcp.mcp_commands.console.print"):
                # Add server
                add_args = argparse.Namespace(
                    name="test_server",
                    transport="http",
                    target="https://api.example.com",
                    args=None,
                    header=["Authorization: Bearer token"],
                    env=None,
                    auth=None,
                )
                handle_mcp_add(add_args)

                # Verify server was added
                assert server_exists("test_server")

                # List servers
                list_args = argparse.Namespace()
                handle_mcp_list(list_args)

                # Get server details
                get_args = argparse.Namespace(name="test_server")
                handle_mcp_get(get_args)

                # Remove server
                remove_args = argparse.Namespace(name="test_server")
                handle_mcp_remove(remove_args)

                # Verify server was removed
                assert not server_exists("test_server")
