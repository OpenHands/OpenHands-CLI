"""MCP command handlers for the CLI interface.

This module provides command handlers for managing MCP server configurations
through the command line interface.
"""

import argparse

from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer
from prompt_toolkit import HTML, print_formatted_text

from openhands_cli.mcp.mcp_display_utils import mask_sensitive_value
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.mcp.mcp_utils import (
    MCPConfigurationError,
    add_server,
    get_server,
    list_servers,
    remove_server,
)


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
        print_formatted_text(
            HTML(f"<{OPENHANDS_THEME.success}>Successfully added MCP server '{args.name}'</{OPENHANDS_THEME.success}>")
        )
    except MCPConfigurationError as e:
        print_formatted_text(HTML(f"<{OPENHANDS_THEME.error}>Error: {e}</{OPENHANDS_THEME.error}>"))
        raise SystemExit(1)


def handle_mcp_remove(args: argparse.Namespace) -> None:
    """Handle the 'mcp remove' command.

    Args:
        args: Parsed command line arguments
    """
    try:
        remove_server(args.name)
        print_formatted_text(
            HTML(f"<{OPENHANDS_THEME.success}>Successfully removed MCP server '{args.name}'</{OPENHANDS_THEME.success}>")
        )
        print_formatted_text(
            HTML(f"<{OPENHANDS_THEME.warning}>Restart your OpenHands session to apply the changes</{OPENHANDS_THEME.warning}>")
        )
    except MCPConfigurationError as e:
        print_formatted_text(HTML(f"<{OPENHANDS_THEME.error}>Error: {e}</{OPENHANDS_THEME.error}>"))
        raise SystemExit(1)


def handle_mcp_list(_args: argparse.Namespace) -> None:
    """Handle the 'mcp list' command.

    Args:
        args: Parsed command line arguments
    """
    try:
        servers = list_servers()

        if not servers:
            print_formatted_text(HTML(f"<{OPENHANDS_THEME.warning}>No MCP servers configured</{OPENHANDS_THEME.warning}>"))
            print_formatted_text(
                HTML(
                    f"Use <{OPENHANDS_THEME.accent}>openhands mcp add</{OPENHANDS_THEME.accent}> to add a server, "
                    f"or create <{OPENHANDS_THEME.accent}>~/.openhands/mcp.json</{OPENHANDS_THEME.accent}> manually"
                )
            )
            return

        print_formatted_text(
            HTML(f"<{OPENHANDS_THEME.foreground}>Configured MCP servers ({len(servers)}):</{OPENHANDS_THEME.foreground}>")
        )
        print_formatted_text("")

        for name, server in servers.items():
            _render_server_details(name, server)
            print_formatted_text("")

    except MCPConfigurationError as e:
        print_formatted_text(HTML(f"<{OPENHANDS_THEME.error}>Error: {e}</{OPENHANDS_THEME.error}>"))
        raise SystemExit(1)


def handle_mcp_get(args: argparse.Namespace) -> None:
    """Handle the 'mcp get' command.

    Args:
        args: Parsed command line arguments
    """
    try:
        server = get_server(args.name)

        print_formatted_text(HTML(f"<{OPENHANDS_THEME.foreground}>MCP server '{args.name}':</{OPENHANDS_THEME.foreground}>"))
        print_formatted_text("")
        _render_server_details(args.name, server, show_name=False)

    except MCPConfigurationError as e:
        print_formatted_text(HTML(f"<{OPENHANDS_THEME.error}>Error: {e}</{OPENHANDS_THEME.error}>"))
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
        print_formatted_text(HTML(f"  <{OPENHANDS_THEME.accent}>• {name}</{OPENHANDS_THEME.accent}>"))

    print_formatted_text(HTML(f"    <{OPENHANDS_THEME.secondary}>Transport:</{OPENHANDS_THEME.secondary}> {server.transport}"))

    # Show authentication method if specified (only for RemoteMCPServer)
    if isinstance(server, RemoteMCPServer) and server.auth:
        print_formatted_text(HTML(f"    <{OPENHANDS_THEME.secondary}>Authentication:</{OPENHANDS_THEME.secondary}> {server.auth}"))

    if isinstance(server, RemoteMCPServer):
        if server.url:
            print_formatted_text(HTML(f"    <{OPENHANDS_THEME.secondary}>URL:</{OPENHANDS_THEME.secondary}> {server.url}"))

        if server.headers:
            print_formatted_text(HTML(f"    <{OPENHANDS_THEME.secondary}>Headers:</{OPENHANDS_THEME.secondary}>"))
            for key, value in server.headers.items():
                # Mask potential sensitive values
                display_value = mask_sensitive_value(key, value)
                print_formatted_text(HTML(f"      {key}: {display_value}"))

    elif isinstance(server, StdioMCPServer):
        if server.command:
            print_formatted_text(HTML(f"    <{OPENHANDS_THEME.secondary}>Command:</{OPENHANDS_THEME.secondary}> {server.command}"))

        if server.args:
            args_str = " ".join(server.args)
            print_formatted_text(HTML(f"    <{OPENHANDS_THEME.secondary}>Arguments:</{OPENHANDS_THEME.secondary}> {args_str}"))

        if server.env:
            print_formatted_text(HTML(f"    <{OPENHANDS_THEME.secondary}>Environment:</{OPENHANDS_THEME.secondary}>"))
            for key, value in server.env.items():
                # Mask potential sensitive values
                display_value = mask_sensitive_value(key, value)
                print_formatted_text(HTML(f"      {key}={display_value}"))


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
        print_formatted_text(HTML(f"<{OPENHANDS_THEME.error}>Unknown MCP command</{OPENHANDS_THEME.error}>"))
        raise SystemExit(1)
