"""Resources tab component for the settings modal.

Displays Skills, Hooks, and MCP servers loaded for the current session.
"""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Static

from openhands.sdk import Agent
from openhands_cli.locations import get_work_dir
from openhands_cli.stores import AgentStore
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.resources import (
    LoadedResourcesInfo,
    collect_loaded_resources,
)


class ResourcesTab(Container):
    """Resources tab component showing Skills, Hooks, and MCP servers."""

    def __init__(self, **kwargs):
        """Initialize the resources tab."""
        super().__init__(**kwargs)
        self._agent: Agent | None = None
        self._resources: LoadedResourcesInfo | None = None
        self._load_resources()

    def _load_resources(self) -> None:
        """Load agent and resource information."""
        try:
            agent_store = AgentStore()
            self._agent = agent_store.load_from_disk()
        except Exception:
            self._agent = None

        self._resources = collect_loaded_resources(
            agent=self._agent, working_dir=get_work_dir()
        )

    def compose(self) -> ComposeResult:
        """Compose the resources tab content."""
        with VerticalScroll(id="resources_content"):
            yield Static(
                "Skills, Hooks, and MCPs",
                classes="form_section_title",
            )
            yield Static(
                "Resources loaded for the current session. "
                "Changes to these require restarting the CLI.",
                classes="form_help",
            )

            # Skills Section
            yield Static("Skills", classes="resources_section_header")
            yield Static(id="skills_content", classes="resources_section_content")

            # Hooks Section
            yield Static("Hooks", classes="resources_section_header")
            yield Static(id="hooks_content", classes="resources_section_content")

            # MCP Servers Section
            yield Static("MCP Servers", classes="resources_section_header")
            yield Static(id="mcp_content", classes="resources_section_content")

    def on_mount(self) -> None:
        """Update content when mounted."""
        self._update_skills_content()
        self._update_hooks_content()
        self._update_mcp_content()

    def _update_skills_content(self) -> None:
        """Update the skills section content."""
        content_widget = self.query_one("#skills_content", Static)
        primary = OPENHANDS_THEME.primary
        secondary = OPENHANDS_THEME.secondary

        if not self._resources or not self._resources.skills:
            content_widget.update(f"[{secondary}]No skills loaded[/{secondary}]")
            return

        lines = []
        for skill in self._resources.skills:
            desc = f" - {skill.description}" if skill.description else ""
            source = (
                f" [{secondary}]({skill.source})[/{secondary}]" if skill.source else ""
            )
            lines.append(f"[{primary}]•[/{primary}] {skill.name}{desc}{source}")

        content_widget.update("\n".join(lines))

    def _update_hooks_content(self) -> None:
        """Update the hooks section content."""
        content_widget = self.query_one("#hooks_content", Static)
        primary = OPENHANDS_THEME.primary
        secondary = OPENHANDS_THEME.secondary

        if not self._resources or not self._resources.hooks:
            content_widget.update(f"[{secondary}]No hooks loaded[/{secondary}]")
            return

        lines = []
        for hook in self._resources.hooks:
            commands_str = ", ".join(hook.commands)
            lines.append(f"[{primary}]•[/{primary}] {hook.hook_type}: {commands_str}")

        content_widget.update("\n".join(lines))

    def _update_mcp_content(self) -> None:
        """Update the MCP servers section content."""
        content_widget = self.query_one("#mcp_content", Static)
        primary = OPENHANDS_THEME.primary
        secondary = OPENHANDS_THEME.secondary
        warning = OPENHANDS_THEME.warning

        if not self._agent:
            content_widget.update(
                f"[{warning}]Unable to load agent configuration[/{warning}]"
            )
            return

        mcp_servers = self._agent.mcp_config.get("mcpServers", {})

        if not mcp_servers:
            content_widget.update(
                f"[{secondary}]No MCP servers configured[/{secondary}]"
            )
            return

        lines = []
        for name, cfg in mcp_servers.items():
            lines.append(f"[{primary}]•[/{primary}] {name}")
            details = self._format_server_details(cfg)
            for detail in details:
                lines.append(f"    {detail}")

        content_widget.update("\n".join(lines))

    def _format_server_details(self, server: Any) -> list[str]:
        """Format server specification details for display."""
        from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer

        from openhands_cli.mcp.mcp_display_utils import normalize_server_object

        details = []
        secondary = OPENHANDS_THEME.secondary

        # Convert to FastMCP object if needed
        server_obj = normalize_server_object(server)

        if isinstance(server_obj, StdioMCPServer):
            details.append(f"[{secondary}]Type: Command-based[/{secondary}]")
            if server_obj.command or server_obj.args:
                command_parts = [server_obj.command] if server_obj.command else []
                if server_obj.args:
                    command_parts.extend(server_obj.args)
                command_str = " ".join(command_parts)
                if command_str:
                    # Truncate long commands
                    if len(command_str) > 50:
                        command_str = command_str[:47] + "..."
                    details.append(f"[{secondary}]Command: {command_str}[/{secondary}]")
        elif isinstance(server_obj, RemoteMCPServer):
            details.append(f"[{secondary}]Type: URL-based[/{secondary}]")
            if server_obj.url:
                url = server_obj.url
                # Truncate long URLs
                if len(url) > 50:
                    url = url[:47] + "..."
                details.append(f"[{secondary}]URL: {url}[/{secondary}]")

        return details
