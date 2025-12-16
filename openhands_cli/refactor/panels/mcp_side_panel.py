"""MCP side panel widget for displaying MCP server information."""

import json
from typing import Any

from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer
from textual.app import App
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Static

from openhands.sdk import Agent
from openhands_cli.locations import MCP_CONFIG_FILE
from openhands_cli.mcp.mcp_display_utils import normalize_server_object
from openhands_cli.mcp.mcp_utils import get_config_status
from openhands_cli.refactor.panels.mcp_panel_style import MCP_PANEL_STYLE
from openhands_cli.theme import OPENHANDS_THEME


class MCPSidePanel(VerticalScroll):
    """Side panel widget that displays MCP server information."""

    DEFAULT_CSS = MCP_PANEL_STYLE

    def __init__(self, agent: Agent | None = None, **kwargs):
        """Initialize the MCP side panel.

        Args:
            agent: The OpenHands agent instance to get MCP config from
        """
        super().__init__(**kwargs)
        self.agent = agent

    @classmethod
    def toggle(cls, app: App) -> None:
        """Toggle the MCP side panel on/off within the given app.

        - If a panel already exists, remove it.
        - If not, create it, mount it into #content_area, and let on_mount()
          refresh the content.
        """
        # Try to find an existing panel
        try:
            existing = app.query_one(cls)
        except NoMatches:
            existing = None

        if existing is not None:
            existing.remove()
            return

        # Otherwise, create a new one and mount it into the content area
        content_area = app.query_one("#content_area", Horizontal)

        # agent = cls._load_agent_safe()
        agent = None
        try:
            from openhands_cli.tui.settings.store import AgentStore

            agent_store = AgentStore()
            agent = agent_store.load()
        except Exception:
            pass

        panel = cls(agent=agent)
        content_area.mount(panel)

    def compose(self):
        """Compose the MCP side panel content."""
        yield Static("MCP Servers", classes="mcp-header")
        yield Static("", id="mcp-content")

    def on_mount(self):
        """Called when the panel is mounted."""
        self.refresh_content()

    def refresh_content(self):
        """Refresh the MCP server content."""
        content_widget = self.query_one("#mcp-content", Static)

        # Check if agent failed to load
        if self.agent is None:
            content_parts = [
                f"[{OPENHANDS_THEME.error}]Failed to load MCP configurations."
                f"[/{OPENHANDS_THEME.error}]",
                f"[{OPENHANDS_THEME.error}]Agent settings file is corrupted!"
                f"[/{OPENHANDS_THEME.error}]",
            ]
            content_widget.update("\n".join(content_parts))
            return

        # Get MCP configuration status
        status = get_config_status()
        current_servers = self.agent.mcp_config.get("mcpServers", {})

        # Build content string
        content_parts = []

        # Show current agent servers
        content_parts.append("[bold]Current Agent Servers:[/bold]")
        if current_servers:
            for name, cfg in current_servers.items():
                content_parts.append(
                    f"[{OPENHANDS_THEME.primary}]• {name}[/{OPENHANDS_THEME.primary}]"
                )
                server_details = self._format_server_details(cfg)
                for detail in server_details:
                    content_parts.append(f"  {detail}")
        else:
            content_parts.append(
                f"[{OPENHANDS_THEME.warning}]  None configured"
                f"[/{OPENHANDS_THEME.warning}]"
            )

        content_parts.append("")

        # Show file status
        if not status["exists"]:
            content_parts.append(
                f"[{OPENHANDS_THEME.warning}]Config file not found"
                f"[/{OPENHANDS_THEME.warning}]"
            )
            content_parts.append(f"Create: ~/.openhands/{MCP_CONFIG_FILE}")
        elif not status["valid"]:
            content_parts.append(
                f"[{OPENHANDS_THEME.error}]Invalid config file"
                f"[/{OPENHANDS_THEME.error}]"
            )
        else:
            content_parts.append(
                f"[{OPENHANDS_THEME.accent}]Config: {len(status['servers'])} "
                f"server(s)[/{OPENHANDS_THEME.accent}]"
            )

            # Show incoming servers if different from current
            incoming_servers = status.get("servers", {})
            if incoming_servers:
                content_parts.append("")
                content_parts.append("[bold]Incoming on Restart:[/bold]")

                # Find new and changed servers
                current_names = set(current_servers.keys())
                incoming_names = set(incoming_servers.keys())
                new_servers = sorted(incoming_names - current_names)

                changed_servers = []
                for name in sorted(incoming_names & current_names):
                    if not self._check_server_specs_are_equal(
                        current_servers[name], incoming_servers[name]
                    ):
                        changed_servers.append(name)

                if new_servers:
                    content_parts.append(
                        f"[{OPENHANDS_THEME.accent}]New:[/{OPENHANDS_THEME.accent}]"
                    )
                    for name in new_servers:
                        content_parts.append(f"  • {name}")

                if changed_servers:
                    content_parts.append(
                        f"[{OPENHANDS_THEME.warning}]Updated:[/{OPENHANDS_THEME.warning}]"
                    )
                    for name in changed_servers:
                        content_parts.append(f"  • {name}")

                if not new_servers and not changed_servers:
                    content_parts.append("  All servers match current")

        # Join all content and update the widget
        content_text = "\n".join(content_parts)
        content_widget.update(content_text)

    def _format_server_details(
        self, server: StdioMCPServer | RemoteMCPServer | dict[str, Any]
    ) -> list[str]:
        """Format server specification details for display."""
        details = []

        # Convert to FastMCP object if needed
        server_obj = normalize_server_object(server)

        if isinstance(server_obj, StdioMCPServer):
            details.append("Type: Command-based")
            if server_obj.command or server_obj.args:
                command_parts = [server_obj.command] if server_obj.command else []
                if server_obj.args:
                    command_parts.extend(server_obj.args)
                command_str = " ".join(command_parts)
                if command_str:
                    details.append(f"Command: {command_str}")
        elif isinstance(server_obj, RemoteMCPServer):
            details.append("Type: URL-based")
            if server_obj.url:
                details.append(f"URL: {server_obj.url}")
            details.append(f"Auth: {server_obj.auth or 'none'}")

        return details

    def _check_server_specs_are_equal(
        self, first_server_spec, second_server_spec
    ) -> bool:
        """Check if two server specifications are equal."""
        first_stringified_server_spec = json.dumps(first_server_spec, sort_keys=True)
        second_stringified_server_spec = json.dumps(second_server_spec, sort_keys=True)
        return first_stringified_server_spec == second_stringified_server_spec
