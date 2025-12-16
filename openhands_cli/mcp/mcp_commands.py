"""MCP command handlers for the CLI interface.

This module provides command handlers for managing MCP server configurations
through the command line interface.
"""

import argparse

from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer
from rich.console import Console

from openhands_cli.mcp.mcp_display_utils import mask_sensitive_value
from openhands_cli.mcp.mcp_utils import (
    MCPConfigurationError,
    add_server,
    get_server,
    list_servers,
    remove_server,
)
from openhands_cli.theme import OPENHANDS_THEME


console = Console()


def handle_mcp_add(args: argparse.Namespace) -> None:
    """Handle the 'mcp add' command.

    Args:
        args: Parsed command line arguments
    """
    try:
        add_server(
            name=args.name,
            transport=args.transport,
            target=args.target,
            args=args.args if args.args else None,
            headers=args.header if args.header else None,
            env_vars=args.env if args.env else None,
            auth=args.auth if args.auth else None,
        )
        console.print(
            f"Successfully added MCP server '{args.name}'",
            style=OPENHANDS_THEME.success,
        )
    except MCPConfigurationError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_mcp_remove(args: argparse.Namespace) -> None:
    """Handle the 'mcp remove' command.

    Args:
        args: Parsed command line arguments
    """
    try:
        remove_server(args.name)
        console.print(
            f"Successfully removed MCP server '{args.name}'",
            style=OPENHANDS_THEME.success,
        )
        console.print(
            "Restart your OpenHands session to apply the changes",
            style=OPENHANDS_THEME.warning,
        )
    except MCPConfigurationError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_mcp_list(_args: argparse.Namespace) -> None:
    """Handle the 'mcp list' command.

    Args:
        args: Parsed command line arguments
    """
    try:
        servers = list_servers()

        if not servers:
            console.print("No MCP servers configured", style=OPENHANDS_THEME.warning)
            console.print(
                "Use [bold]openhands mcp add[/bold] to add a server, "
                "or create [bold]~/.openhands/mcp.json[/bold] manually",
                style=OPENHANDS_THEME.accent,
            )
            return

        console.print(
            f"Configured MCP servers ({len(servers)}):",
            style=OPENHANDS_THEME.foreground,
        )
        console.print()

        for name, server in servers.items():
            _render_server_details(name, server)
            console.print()

    except MCPConfigurationError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_mcp_get(args: argparse.Namespace) -> None:
    """Handle the 'mcp get' command.

    Args:
        args: Parsed command line arguments
    """
    try:
        server = get_server(args.name)

        console.print(f"MCP server '{args.name}':", style=OPENHANDS_THEME.foreground)
        console.print()
        _render_server_details(args.name, server, show_name=False)

    except MCPConfigurationError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def _render_server_details(
    name: str, server: StdioMCPServer | RemoteMCPServer, show_name: bool = True
) -> None:
    """Render server configuration details.

    Args:
        name: Server name
        server: Server object
        show_name: Whether to show the server name
    """
    if show_name:
        console.print(f"  • {name}", style=OPENHANDS_THEME.accent)

    console.print(f"    Transport: {server.transport}", style=OPENHANDS_THEME.secondary)

    # Show authentication method if specified (only for RemoteMCPServer)
    if isinstance(server, RemoteMCPServer) and server.auth:
        console.print(
            f"    Authentication: {server.auth}", style=OPENHANDS_THEME.secondary
        )

    if isinstance(server, RemoteMCPServer):
        if server.url:
            console.print(f"    URL: {server.url}", style=OPENHANDS_THEME.secondary)

        if server.headers:
            console.print("    Headers:", style=OPENHANDS_THEME.secondary)
            for key, value in server.headers.items():
                # Mask potential sensitive values
                display_value = mask_sensitive_value(key, value)
                console.print(f"      {key}: {display_value}")

    elif isinstance(server, StdioMCPServer):
        if server.command:
            console.print(
                f"    Command: {server.command}", style=OPENHANDS_THEME.secondary
            )

        if server.args:
            args_str = " ".join(server.args)
            console.print(f"    Arguments: {args_str}", style=OPENHANDS_THEME.secondary)

        if server.env:
            console.print("    Environment:", style=OPENHANDS_THEME.secondary)
            for key, value in server.env.items():
                # Mask potential sensitive values
                display_value = mask_sensitive_value(key, value)
                console.print(f"      {key}={display_value}")


def handle_mcp_command(args: argparse.Namespace) -> None:
    """Main handler for MCP commands.

    Args:
        args: Parsed command line arguments
    """
    if args.mcp_command == "add":
        handle_mcp_add(args)
    elif args.mcp_command == "remove":
        handle_mcp_remove(args)
    elif args.mcp_command == "list":
        handle_mcp_list(args)
    elif args.mcp_command == "get":
        handle_mcp_get(args)
    else:
        console.print("Unknown MCP command", style=OPENHANDS_THEME.error)
        raise SystemExit(1)
