"""Tests for MCPSidePanel widget."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from openhands_cli.tui.panels.mcp_side_panel import MCPSidePanel


if TYPE_CHECKING:
    pass


def _create_mock_agent(mcp_config: dict[str, Any] | None = None) -> Any:
    """Create a mock Agent with MCP configuration."""
    mock_agent = MagicMock()
    mock_agent.mcp_config = mcp_config or {"mcpServers": {}}
    return mock_agent


# ============================================================================
# Test App Helper
# ============================================================================


class MCPPanelTestApp(App):
    """Test app for mounting MCPSidePanel."""

    CSS = """
    Screen { layout: horizontal; }
    #main_content { width: 2fr; }
    """

    def __init__(self, agent: Any = None, **kwargs):
        super().__init__(**kwargs)
        self._agent = agent

    def compose(self) -> ComposeResult:
        with Horizontal(id="content_area"):
            yield Static("Main content", id="main_content")


# ============================================================================
# _check_server_specs_are_equal Tests
# ============================================================================


class TestCheckServerSpecsAreEqual:
    """Tests for MCPSidePanel._check_server_specs_are_equal method."""

    def test_equal_dict_specs(self):
        """Verify equal dict specs return True."""
        mock_agent = _create_mock_agent()
        panel = MCPSidePanel(agent=mock_agent)

        spec1 = {"url": "https://example.com", "transport": "http"}
        spec2 = {"url": "https://example.com", "transport": "http"}

        result = panel._check_server_specs_are_equal(spec1, spec2)
        assert result is True

    def test_different_dict_specs(self):
        """Verify different dict specs return False."""
        mock_agent = _create_mock_agent()
        panel = MCPSidePanel(agent=mock_agent)

        spec1 = {"url": "https://example.com", "transport": "http"}
        spec2 = {"url": "https://other.com", "transport": "http"}

        result = panel._check_server_specs_are_equal(spec1, spec2)
        assert result is False

    def test_remote_mcp_server_objects_are_serializable(self):
        """Test that RemoteMCPServer objects can be compared without JSON error.

        This test reproduces the bug from issue #362 where RemoteMCPServer
        objects caused TypeError: Object of type RemoteMCPServer is not JSON
        serializable.
        """
        mock_agent = _create_mock_agent()
        panel = MCPSidePanel(agent=mock_agent)

        # Create RemoteMCPServer objects (as they would be in agent.mcp_config)
        server1 = RemoteMCPServer(
            url="https://api.example.com",
            transport="http",
            headers={"Authorization": "Bearer token"},
        )
        server2 = RemoteMCPServer(
            url="https://api.example.com",
            transport="http",
            headers={"Authorization": "Bearer token"},
        )

        # This should NOT raise TypeError
        result = panel._check_server_specs_are_equal(server1, server2)
        assert result is True

    def test_stdio_mcp_server_objects_are_serializable(self):
        """Test that StdioMCPServer objects can be compared without JSON error."""
        mock_agent = _create_mock_agent()
        panel = MCPSidePanel(agent=mock_agent)

        # Create StdioMCPServer objects
        server1 = StdioMCPServer(
            command="python",
            args=["-m", "server"],
            transport="stdio",
            env={"API_KEY": "secret"},
        )
        server2 = StdioMCPServer(
            command="python",
            args=["-m", "server"],
            transport="stdio",
            env={"API_KEY": "secret"},
        )

        # This should NOT raise TypeError
        result = panel._check_server_specs_are_equal(server1, server2)
        assert result is True

    def test_mixed_server_and_dict_comparison(self):
        """Test comparing a server object with a dict representation."""
        mock_agent = _create_mock_agent()
        panel = MCPSidePanel(agent=mock_agent)

        # RemoteMCPServer object (from agent.mcp_config)
        server_obj = RemoteMCPServer(
            url="https://api.example.com",
            transport="http",
        )

        # Dict representation (from get_config_status)
        server_dict = {
            "url": "https://api.example.com",
            "transport": "http",
        }

        # This should NOT raise TypeError
        result = panel._check_server_specs_are_equal(server_obj, server_dict)
        # The result may be True or False depending on implementation,
        # but it should not raise an exception
        assert isinstance(result, bool)

    def test_different_remote_mcp_servers(self):
        """Test that different RemoteMCPServer objects return False."""
        mock_agent = _create_mock_agent()
        panel = MCPSidePanel(agent=mock_agent)

        server1 = RemoteMCPServer(
            url="https://api.example.com",
            transport="http",
        )
        server2 = RemoteMCPServer(
            url="https://other.example.com",
            transport="http",
        )

        result = panel._check_server_specs_are_equal(server1, server2)
        assert result is False


# ============================================================================
# refresh_content Tests with MCP Server Objects
# ============================================================================


class TestRefreshContentWithServerObjects:
    """Tests for MCPSidePanel.refresh_content with server objects."""

    @pytest.mark.asyncio
    async def test_refresh_content_with_remote_mcp_servers(self, tmp_path: Path):
        """Test refresh_content handles RemoteMCPServer objects in agent config.

        This test reproduces the bug from issue #362 where opening the MCP menu
        crashed with: TypeError: Object of type RemoteMCPServer is not JSON serializable
        """
        # Create MCP config file with servers
        mcp_config_data = {
            "mcpServers": {
                "test_server": {
                    "url": "https://api.example.com",
                    "transport": "http",
                }
            }
        }
        mcp_config_file = tmp_path / "mcp.json"
        mcp_config_file.write_text(json.dumps(mcp_config_data))

        # Create agent with RemoteMCPServer objects (as they would be loaded)
        agent_mcp_config = {
            "mcpServers": {
                "test_server": RemoteMCPServer(
                    url="https://api.example.com",
                    transport="http",
                )
            }
        }
        mock_agent = _create_mock_agent(agent_mcp_config)

        class TestApp(App):
            CSS = """
            Screen { layout: horizontal; }
            """

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content", id="main_content")

        app = TestApp()

        with patch("openhands_cli.locations.PERSISTENCE_DIR", str(tmp_path)):
            async with app.run_test() as pilot:
                await pilot.pause()

                panel = MCPSidePanel(agent=mock_agent)
                content_area = app.query_one("#content_area", Horizontal)
                content_area.mount(panel)
                await pilot.pause()

                # This should NOT raise TypeError
                panel.refresh_content()

    @pytest.mark.asyncio
    async def test_refresh_content_with_disabled_servers(self, tmp_path: Path):
        """Test refresh_content handles disabled servers (issue #362 scenario).

        The user mentioned having some MCP servers explicitly disabled.
        """
        # Create MCP config file with enabled and disabled servers
        mcp_config_data = {
            "mcpServers": {
                "enabled_server": {
                    "url": "https://enabled.example.com",
                    "transport": "http",
                    "enabled": True,
                },
                "disabled_server": {
                    "url": "https://disabled.example.com",
                    "transport": "http",
                    "enabled": False,
                },
            }
        }
        mcp_config_file = tmp_path / "mcp.json"
        mcp_config_file.write_text(json.dumps(mcp_config_data))

        # Create agent with RemoteMCPServer objects
        agent_mcp_config = {
            "mcpServers": {
                "enabled_server": RemoteMCPServer(
                    url="https://enabled.example.com",
                    transport="http",
                ),
                "disabled_server": RemoteMCPServer(
                    url="https://disabled.example.com",
                    transport="http",
                ),
            }
        }
        mock_agent = _create_mock_agent(agent_mcp_config)

        class TestApp(App):
            CSS = """
            Screen { layout: horizontal; }
            """

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content", id="main_content")

        app = TestApp()

        with patch("openhands_cli.locations.PERSISTENCE_DIR", str(tmp_path)):
            async with app.run_test() as pilot:
                await pilot.pause()

                panel = MCPSidePanel(agent=mock_agent)
                content_area = app.query_one("#content_area", Horizontal)
                content_area.mount(panel)
                await pilot.pause()

                # This should NOT raise TypeError
                panel.refresh_content()


# ============================================================================
# toggle Tests
# ============================================================================


class TestToggle:
    """Tests for MCPSidePanel.toggle class method."""

    @pytest.mark.asyncio
    async def test_toggle_mounts_panel(self, tmp_path: Path):
        """Verify toggle() mounts the panel."""
        app = MCPPanelTestApp()

        with patch("openhands_cli.locations.PERSISTENCE_DIR", str(tmp_path)):
            async with app.run_test() as pilot:
                await pilot.pause()

                # Toggle to mount
                MCPSidePanel.toggle(app)
                await pilot.pause()

                # Verify panel is mounted
                panels = app.query(MCPSidePanel)
                assert len(panels) == 1

    @pytest.mark.asyncio
    async def test_toggle_removes_panel(self, tmp_path: Path):
        """Verify toggle() removes an existing panel."""
        app = MCPPanelTestApp()

        with patch("openhands_cli.locations.PERSISTENCE_DIR", str(tmp_path)):
            async with app.run_test() as pilot:
                await pilot.pause()

                # Toggle to mount
                MCPSidePanel.toggle(app)
                await pilot.pause()

                # Toggle to remove
                MCPSidePanel.toggle(app)
                await pilot.pause()

                # Verify panel is removed
                panels = app.query(MCPSidePanel)
                assert len(panels) == 0

    @pytest.mark.asyncio
    async def test_toggle_with_remote_mcp_servers_in_agent(self, tmp_path: Path):
        """Test toggle works when agent has RemoteMCPServer objects.

        This is the main reproduction test for issue #362.
        """
        # Create MCP config file
        mcp_config_data = {
            "mcpServers": {
                "notion": {
                    "url": "https://mcp.notion.com/mcp",
                    "transport": "http",
                    "auth": "oauth",
                }
            }
        }
        mcp_config_file = tmp_path / "mcp.json"
        mcp_config_file.write_text(json.dumps(mcp_config_data))

        # Create agent settings with RemoteMCPServer objects
        agent_mcp_config = {
            "mcpServers": {
                "notion": RemoteMCPServer(
                    url="https://mcp.notion.com/mcp",
                    transport="http",
                    auth="oauth",
                )
            }
        }

        # Create a mock agent that will be returned by AgentStore.load()
        mock_agent = _create_mock_agent(agent_mcp_config)

        app = MCPPanelTestApp()

        with (
            patch("openhands_cli.locations.PERSISTENCE_DIR", str(tmp_path)),
            patch("openhands_cli.stores.AgentStore") as mock_agent_store_class,
        ):
            mock_agent_store = MagicMock()
            mock_agent_store.load.return_value = mock_agent
            mock_agent_store_class.return_value = mock_agent_store

            async with app.run_test() as pilot:
                await pilot.pause()

                # This should NOT raise TypeError
                MCPSidePanel.toggle(app)
                await pilot.pause()

                # Verify panel is mounted
                panels = app.query(MCPSidePanel)
                assert len(panels) == 1
