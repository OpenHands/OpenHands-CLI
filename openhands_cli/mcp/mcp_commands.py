"""MCP command handlers for the CLI interface.

This module provides command handlers for managing MCP server configurations
through the command line interface.
"""

import argparse

from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer
from prompt_toolkit import HTML, print_formatted_text

from openhands_cli.mcp.mcp_display_utils import mask_sensitive_value
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
            HTML(f"<green>Successfully added MCP server '{args.name}'</green>")
        )
    except MCPConfigurationError as e:
        print_formatted_text(HTML(f"<red>Error: {e}</red>"))
        raise SystemExit(1)


def handle_mcp_remove(args: argparse.Namespace) -> None:
    """Handle the 'mcp remove' command.

    Args:
        args: Parsed command line arguments
    """
    try:
        remove_server(args.name)
        print_formatted_text(
            HTML(f"<green>Successfully removed MCP server '{args.name}'</green>")
        )
        print_formatted_text(
            HTML("<yellow>Restart your OpenHands session to apply the changes</yellow>")
        )
    except MCPConfigurationError as e:
        print_formatted_text(HTML(f"<red>Error: {e}</red>"))
        raise SystemExit(1)


def handle_mcp_list(_args: argparse.Namespace) -> None:
    """Handle the 'mcp list' command.

    Args:
        args: Parsed command line arguments
    """
    try:
        servers = list_servers()

        if not servers:
            print_formatted_text(HTML("<yellow>No MCP servers configured</yellow>"))
            print_formatted_text(
                HTML(
                    "Use <cyan>openhands mcp add</cyan> to add a server, "
                    "or create <cyan>~/.openhands/mcp.json</cyan> manually"
                )
            )
            return

        print_formatted_text(
            HTML(f"<white>Configured MCP servers ({len(servers)}):</white>")
        )
        print_formatted_text("")

        for name, server in servers.items():
            _render_server_details(name, server)
            print_formatted_text("")

    except MCPConfigurationError as e:
        print_formatted_text(HTML(f"<red>Error: {e}</red>"))
        raise SystemExit(1)


def handle_mcp_get(args: argparse.Namespace) -> None:
    """Handle the 'mcp get' command.

    Args:
        args: Parsed command line arguments
    """
    try:
        server = get_server(args.name)

        print_formatted_text(HTML(f"<white>MCP server '{args.name}':</white>"))
        print_formatted_text("")
        _render_server_details(args.name, server, show_name=False)

    except MCPConfigurationError as e:
        print_formatted_text(HTML(f"<red>Error: {e}</red>"))
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
        print_formatted_text(HTML(f"  <cyan>• {name}</cyan>"))

    print_formatted_text(HTML(f"    <grey>Transport:</grey> {server.transport}"))

    # Show authentication method if specified (only for RemoteMCPServer)
    if isinstance(server, RemoteMCPServer) and server.auth:
        print_formatted_text(HTML(f"    <grey>Authentication:</grey> {server.auth}"))

    if isinstance(server, RemoteMCPServer):
        if server.url:
            print_formatted_text(HTML(f"    <grey>URL:</grey> {server.url}"))

        if server.headers:
            print_formatted_text(HTML("    <grey>Headers:</grey>"))
            for key, value in server.headers.items():
                # Mask potential sensitive values
                display_value = mask_sensitive_value(key, value)
                print_formatted_text(HTML(f"      {key}: {display_value}"))

    elif isinstance(server, StdioMCPServer):
        if server.command:
            print_formatted_text(HTML(f"    <grey>Command:</grey> {server.command}"))

        if server.args:
            args_str = " ".join(server.args)
            print_formatted_text(HTML(f"    <grey>Arguments:</grey> {args_str}"))

        if server.env:
            print_formatted_text(HTML("    <grey>Environment:</grey>"))
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
        print_formatted_text(HTML("<red>Unknown MCP command</red>"))
        raise SystemExit(1)
