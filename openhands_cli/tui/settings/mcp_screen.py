import json
from pathlib import Path
from typing import Any

from fastmcp.mcp_config import MCPConfig, RemoteMCPServer, StdioMCPServer
from prompt_toolkit import HTML, print_formatted_text

from openhands.sdk import Agent
from openhands_cli.locations import MCP_CONFIG_FILE, PERSISTENCE_DIR
from openhands_cli.mcp.mcp_display_utils import normalize_server_object


class MCPScreen:
    """
    MCP Screen

    1. Display information about setting up MCP
    2. See existing servers that are setup
    3. Debug additional servers passed via mcp.json
    4. Identify servers waiting to sync on session restart
    """

    # ---------- server spec handlers ----------

    def _check_server_specs_are_equal(
        self, first_server_spec, second_server_spec
    ) -> bool:
        first_stringified_server_spec = json.dumps(first_server_spec, sort_keys=True)
        second_stringified_server_spec = json.dumps(second_server_spec, sort_keys=True)
        return first_stringified_server_spec == second_stringified_server_spec

    def _check_mcp_config_status(self) -> dict:
        """Check the status of the MCP configuration file and return information
        about it."""
        config_path = Path(PERSISTENCE_DIR) / MCP_CONFIG_FILE

        if not config_path.exists():
            return {
                "exists": False,
                "valid": False,
                "servers": {},
                "message": (
                    f"MCP configuration file not found at "
                    f"~/.openhands/{MCP_CONFIG_FILE}"
                ),
            }

        try:
            mcp_config = MCPConfig.from_file(config_path)
            servers = mcp_config.to_dict().get("mcpServers", {})
            return {
                "exists": True,
                "valid": True,
                "servers": servers,
                "message": (
                    f"Valid MCP configuration found with {len(servers)} server(s)"
                ),
            }
        except Exception as e:
            return {
                "exists": True,
                "valid": False,
                "servers": {},
                "message": f"Invalid MCP configuration file: {str(e)}",
            }

    # ---------- TUI helpers ----------

    def _get_mcp_server_diff(
        self,
        current: dict[str, Any],
        incoming: dict[str, Any],
    ) -> None:
        """
        Display a diff-style view:

        - Always show the MCP servers the agent is *currently* configured with
        - If there are incoming servers (from ~/.openhands/mcp.json),
          clearly show which ones are NEW (not in current) and which ones are CHANGED
          (same name but different config). Unchanged servers are not repeated.
        """

        print_formatted_text(HTML("<white>Current Agent MCP Servers:</white>"))
        if current:
            for name, cfg in current.items():
                self._render_server_summary(name, cfg, indent=2)
        else:
            print_formatted_text(
                HTML("  <yellow>None configured on the current agent.</yellow>")
            )
        print_formatted_text("")

        # If no incoming, we're done
        if not incoming:
            print_formatted_text(
                HTML("<grey>No incoming servers detected for next restart.</grey>")
            )
            print_formatted_text("")
            return

        # Compare names and configs
        current_names = set(current.keys())
        incoming_names = set(incoming.keys())
        new_servers = sorted(incoming_names - current_names)

        overriden_servers = []
        for name in sorted(incoming_names & current_names):
            if not self._check_server_specs_are_equal(current[name], incoming[name]):
                overriden_servers.append(name)

        # Display incoming section header
        print_formatted_text(
            HTML(
                "<white>Incoming Servers on Restart "
                "(from ~/.openhands/mcp.json):</white>"
            )
        )

        if not new_servers and not overriden_servers:
            print_formatted_text(
                HTML(
                    "  <grey>All configured servers match the current agent "
                    "configuration.</grey>"
                )
            )
            print_formatted_text("")
            return

        if new_servers:
            print_formatted_text(HTML("  <green>New servers (will be added):</green>"))
            for name in new_servers:
                self._render_server_summary(name, incoming[name], indent=4)

        if overriden_servers:
            print_formatted_text(
                HTML("  <yellow>Updated servers (configuration will change):</yellow>")
            )
            for name in overriden_servers:
                print_formatted_text(HTML(f"    <white>• {name}</white>"))
                print_formatted_text(HTML("      <grey>Current:</grey>"))
                self._render_server_summary(None, current[name], indent=8)
                print_formatted_text(HTML("      <grey>Incoming:</grey>"))
                self._render_server_summary(None, incoming[name], indent=8)

        print_formatted_text("")

    def _render_server_summary(
        self,
        server_name: str | None,
        server: StdioMCPServer | RemoteMCPServer | dict[str, Any],
        indent: int = 2,
    ) -> None:
        pad = " " * indent

        if server_name:
            print_formatted_text(HTML(f"{pad}<white>• {server_name}</white>"))

        # Convert to FastMCP object if needed
        server_obj = normalize_server_object(server)

        if isinstance(server_obj, StdioMCPServer):
            print_formatted_text(HTML(f"{pad}  <grey>Type: Command-based</grey>"))
            if server_obj.command or server_obj.args:
                command_parts = [server_obj.command] if server_obj.command else []
                if server_obj.args:
                    command_parts.extend(server_obj.args)
                command_str = " ".join(command_parts)
                if command_str:
                    print_formatted_text(
                        HTML(f"{pad}  <grey>Command: {command_str}</grey>")
                    )
        elif isinstance(server_obj, RemoteMCPServer):
            print_formatted_text(HTML(f"{pad}  <grey>Type: URL-based</grey>"))
            if server_obj.url:
                print_formatted_text(HTML(f"{pad}  <grey>URL: {server_obj.url}</grey>"))
            print_formatted_text(
                HTML(f"{pad}  <grey>Auth: {server_obj.auth or 'none'}</grey>")
            )

    def _display_information_header(self) -> None:
        print_formatted_text(
            HTML("<gold>MCP (Model Context Protocol) Configuration</gold>")
        )
        print_formatted_text("")
        print_formatted_text(HTML("<white>To get started:</white>"))
        print_formatted_text(
            HTML(
                "  1. Create the configuration file: <cyan>~/.openhands/mcp.json</cyan>"
            )
        )
        print_formatted_text(
            HTML(
                "  2. Add your MCP server configurations "
                "<cyan>https://gofastmcp.com/clients/client#configuration-format</cyan>"
            )
        )
        print_formatted_text(
            HTML("  3. Restart your OpenHands session to load the new configuration")
        )
        print_formatted_text("")

    # ---------- status + display entrypoint ----------

    def display_mcp_info(self, existing_agent: Agent) -> None:
        """Display comprehensive MCP configuration information."""

        self._display_information_header()

        # Always determine current & incoming first
        status = self._check_mcp_config_status()
        incoming_servers = status.get("servers", {}) if status.get("valid") else {}
        current_servers = existing_agent.mcp_config.get("mcpServers", {})

        # Show file status
        if not status["exists"]:
            print_formatted_text(
                HTML("<yellow>Status: Configuration file not found</yellow>")
            )

        elif not status["valid"]:
            print_formatted_text(HTML(f"<red>Status: {status['message']}</red>"))
            print_formatted_text("")
            print_formatted_text(
                HTML("<white>Please check your configuration file format.</white>")
            )
        else:
            print_formatted_text(HTML(f"<green>Status: {status['message']}</green>"))

        print_formatted_text("")

        # Always show the agent's current servers
        # Then show incoming (deduped and changes highlighted)
        self._get_mcp_server_diff(current_servers, incoming_servers)
