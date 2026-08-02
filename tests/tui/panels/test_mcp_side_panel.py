"""Tests for MCPSidePanel widget."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from openhands.sdk.mcp.config import MCPOAuthAuthCredential, MCPServer
from openhands_cli.stores.agent_store import convert_mcp_servers
from openhands_cli.tui.panels.mcp_side_panel import MCPSidePanel
from tests.conftest import MockLocations


if TYPE_CHECKING:
    pass


def _create_mock_agent(mcp_config: dict[str, Any] | None = None) -> Any:
    """Create a mock Agent with MCP configuration."""
    mock_agent = MagicMock()
    mock_agent.mcp_config = mcp_config or {}
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

    def test_equal_mcp_server_objects(self):
        """Verify equal MCPServer specs return True."""
        panel = MCPSidePanel(agent=_create_mock_agent())

        spec1 = MCPServer(url="https://example.com", transport="http")
        spec2 = MCPServer(url="https://example.com", transport="http")

        assert panel._check_server_specs_are_equal(spec1, spec2) is True

    def test_different_mcp_server_objects(self):
        """Verify different MCPServer specs return False."""
        panel = MCPSidePanel(agent=_create_mock_agent())

        spec1 = MCPServer(url="https://example.com", transport="http")
        spec2 = MCPServer(url="https://other.com", transport="http")

        assert panel._check_server_specs_are_equal(spec1, spec2) is False

    def test_mcp_server_object_vs_raw_dict(self):
        """Compare an MCPServer (current) with a raw mcp.json dict (incoming).

        This is the shape of the "Incoming on Restart" comparison: the
        persisted agent holds MCPServer objects while get_config_status()
        returns raw dicts. Equal configurations must compare equal.
        """
        panel = MCPSidePanel(agent=_create_mock_agent())

        current = MCPServer(url="https://api.example.com", transport="http")
        incoming = {"url": "https://api.example.com", "transport": "http"}

        assert panel._check_server_specs_are_equal(current, incoming) is True

    def test_mcp_server_object_vs_changed_raw_dict(self):
        """A modified incoming dict must compare unequal."""
        panel = MCPSidePanel(agent=_create_mock_agent())

        current = MCPServer(url="https://api.example.com", transport="http")
        incoming = {"url": "https://api.example.com", "transport": "sse"}

        assert panel._check_server_specs_are_equal(current, incoming) is False

    def test_mcp_server_with_string_auth_vs_raw_dict(self):
        """fastmcp-style string auth in mcp.json matches the coerced current."""
        panel = MCPSidePanel(agent=_create_mock_agent())

        current = convert_mcp_servers(
            {"s": {"url": "https://mcp.notion.com/mcp", "auth": "oauth"}}
        )["s"]
        incoming = {"url": "https://mcp.notion.com/mcp", "auth": "oauth"}

        assert panel._check_server_specs_are_equal(current, incoming) is True

    def test_uncoercible_incoming_dict_does_not_raise(self):
        """An invalid incoming spec is reported as changed, not an error."""
        panel = MCPSidePanel(agent=_create_mock_agent())

        current = MCPServer(url="https://api.example.com", transport="http")
        incoming = {"transport": "stdio"}  # missing required command

        assert panel._check_server_specs_are_equal(current, incoming) is False


# ============================================================================
# refresh_content Tests with MCP Server Objects
# ============================================================================


class TestRefreshContentWithServerObjects:
    """Tests for MCPSidePanel.refresh_content with server objects."""

    @pytest.mark.asyncio
    async def test_refresh_content_with_remote_mcp_servers(
        self, mock_locations: MockLocations
    ):
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
        mcp_config_file = mock_locations.persistence_dir / "mcp.json"
        mcp_config_file.write_text(json.dumps(mcp_config_data))

        # Create agent with MCPServer objects (as they would be loaded from mcp.json)
        agent_mcp_config = {
            "test_server": MCPServer(
                url="https://api.example.com",
                transport="http",
            )
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

        async with app.run_test() as pilot:
            await pilot.pause()

            panel = MCPSidePanel(agent=mock_agent)
            content_area = app.query_one("#content_area", Horizontal)
            content_area.mount(panel)
            await pilot.pause()

            # This should NOT raise TypeError
            panel.refresh_content()

    @pytest.mark.asyncio
    async def test_refresh_content_with_disabled_servers(
        self, mock_locations: MockLocations
    ):
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
        mcp_config_file = mock_locations.persistence_dir / "mcp.json"
        mcp_config_file.write_text(json.dumps(mcp_config_data))

        # Create agent with MCPServer objects
        agent_mcp_config = {
            "enabled_server": MCPServer(
                url="https://enabled.example.com",
                transport="http",
            ),
            "disabled_server": MCPServer(
                url="https://disabled.example.com",
                transport="http",
            ),
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

        async with app.run_test() as pilot:
            await pilot.pause()

            panel = MCPSidePanel(agent=mock_agent)
            content_area = app.query_one("#content_area", Horizontal)
            content_area.mount(panel)
            await pilot.pause()

            # This should NOT raise TypeError
            panel.refresh_content()


# ============================================================================
# Incoming on Restart section Tests
# ============================================================================


class TestIncomingOnRestart:
    """Tests for the Incoming on Restart section of refresh_content."""

    @pytest.mark.asyncio
    async def test_incoming_section_shows_new_and_updated(
        self, mock_locations: MockLocations
    ):
        """New and changed mcp.json servers are listed for the next restart."""
        mcp_config_data = {
            "mcpServers": {
                "unchanged": {"url": "https://same.example.com", "transport": "http"},
                "updated": {"url": "https://new-url.example.com", "transport": "http"},
                "brand_new": {"command": "npx", "args": ["-y", "srv"]},
            }
        }
        mcp_config_file = mock_locations.persistence_dir / "mcp.json"
        mcp_config_file.write_text(json.dumps(mcp_config_data))

        mock_agent = _create_mock_agent(
            {
                "unchanged": MCPServer(
                    url="https://same.example.com", transport="http"
                ),
                "updated": MCPServer(
                    url="https://old-url.example.com", transport="http"
                ),
            }
        )

        app = MCPPanelTestApp()

        async with app.run_test() as pilot:
            await pilot.pause()

            panel = MCPSidePanel(agent=mock_agent)
            content_area = app.query_one("#content_area", Horizontal)
            content_area.mount(panel)
            await pilot.pause()

            content = str(app.query_one("#mcp-content", Static).content)
            assert "Incoming on Restart:" in content
            assert "New:" in content
            assert "brand_new" in content
            assert "Updated:" in content
            assert "updated" in content

    @pytest.mark.asyncio
    async def test_incoming_section_all_match(self, mock_locations: MockLocations):
        """Identical mcp.json servers report as matching current."""
        mcp_config_data = {
            "mcpServers": {
                "same": {"url": "https://same.example.com", "transport": "http"},
            }
        }
        mcp_config_file = mock_locations.persistence_dir / "mcp.json"
        mcp_config_file.write_text(json.dumps(mcp_config_data))

        mock_agent = _create_mock_agent(
            {"same": MCPServer(url="https://same.example.com", transport="http")}
        )

        app = MCPPanelTestApp()

        async with app.run_test() as pilot:
            await pilot.pause()

            panel = MCPSidePanel(agent=mock_agent)
            content_area = app.query_one("#content_area", Horizontal)
            content_area.mount(panel)
            await pilot.pause()

            content = str(app.query_one("#mcp-content", Static).content)
            assert "Incoming on Restart:" in content
            assert "All servers match current" in content


# ============================================================================
# toggle Tests
# ============================================================================


class TestToggle:
    """Tests for MCPSidePanel.toggle class method."""

    @pytest.mark.asyncio
    async def test_toggle_mounts_panel(self, mock_locations: MockLocations):
        """Verify toggle() mounts the panel."""
        app = MCPPanelTestApp()

        async with app.run_test() as pilot:
            await pilot.pause()

            # Toggle to mount
            MCPSidePanel.toggle(app)
            await pilot.pause()

            # Verify panel is mounted
            panels = app.query(MCPSidePanel)
            assert len(panels) == 1

    @pytest.mark.asyncio
    async def test_toggle_removes_panel(self, mock_locations: MockLocations):
        """Verify toggle() removes an existing panel."""
        app = MCPPanelTestApp()

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
    async def test_toggle_with_remote_mcp_servers_in_agent(
        self, mock_locations: MockLocations
    ):
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
        mcp_config_file = mock_locations.persistence_dir / "mcp.json"
        mcp_config_file.write_text(json.dumps(mcp_config_data))

        # Create agent settings with MCPServer objects
        agent_mcp_config = {
            "notion": MCPServer(
                url="https://mcp.notion.com/mcp",
                transport="http",
                auth=MCPOAuthAuthCredential(strategy="oauth2"),
            )
        }

        # Create a mock agent that will be returned by AgentStore.load()
        mock_agent = _create_mock_agent(agent_mcp_config)

        app = MCPPanelTestApp()

        with patch("openhands_cli.stores.AgentStore") as mock_agent_store_class:
            mock_agent_store = MagicMock()
            mock_agent_store.load_from_disk.return_value = mock_agent
            mock_agent_store_class.return_value = mock_agent_store

            async with app.run_test() as pilot:
                await pilot.pause()

                # This should NOT raise TypeError
                MCPSidePanel.toggle(app)
                await pilot.pause()

                # Verify panel is mounted
                panels = app.query(MCPSidePanel)
                assert len(panels) == 1
