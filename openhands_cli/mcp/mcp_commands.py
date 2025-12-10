"""MCP command handlers for the CLI interface.

This module provides command handlers for managing MCP server configurations
through the command line interface.
"""

import argparse
from typing import Any

from prompt_toolkit import HTML, print_formatted_text

from openhands_cli.mcp.mcp_display_utils import (
    extract_server_info,
    mask_sensitive_value,
)
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

        for name, config in servers.items():
            _render_server_details(name, config)
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
        config = get_server(args.name)

        print_formatted_text(HTML(f"<white>MCP server '{args.name}':</white>"))
        print_formatted_text("")
        _render_server_details(args.name, config, show_name=False)

    except MCPConfigurationError as e:
        print_formatted_text(HTML(f"<red>Error: {e}</red>"))
        raise SystemExit(1)


def _render_server_details(
    name: str, config: dict[str, Any], show_name: bool = True
) -> None:
    """Render server configuration details.

    Args:
        name: Server name
        config: Server configuration
        show_name: Whether to show the server name
    """
    if show_name:
        print_formatted_text(HTML(f"  <cyan>• {name}</cyan>"))

    info = extract_server_info(config)
    print_formatted_text(HTML(f"    <grey>Transport:</grey> {info['transport_type']}"))

    # Show authentication method if specified
    if info["auth"]:
        print_formatted_text(HTML(f"    <grey>Authentication:</grey> {info['auth']}"))

    if info["transport_type"] in ["http", "sse"]:
        if info["url"]:
            print_formatted_text(HTML(f"    <grey>URL:</grey> {info['url']}"))

        if info["headers"]:
            print_formatted_text(HTML("    <grey>Headers:</grey>"))
            for key, value in info["headers"].items():
                # Mask potential sensitive values
                display_value = mask_sensitive_value(key, value)
                print_formatted_text(HTML(f"      {key}: {display_value}"))

    elif info["transport_type"] == "stdio":
        if info["command"]:
            print_formatted_text(HTML(f"    <grey>Command:</grey> {info['command']}"))

        if info["args"]:
            args_str = " ".join(info["args"])
            print_formatted_text(HTML(f"    <grey>Arguments:</grey> {args_str}"))

        if info["env"]:
            print_formatted_text(HTML("    <grey>Environment:</grey>"))
            for key, value in info["env"].items():
                # Mask potential sensitive values
                display_value = mask_sensitive_value(key, value)
                print_formatted_text(HTML(f"      {key}={display_value}"))


def handle_mcp_command(
    args: argparse.Namespace, mcp_parser: argparse.ArgumentParser | None = None
) -> None:
    """Main handler for MCP commands.

    Args:
        args: Parsed command line arguments
        mcp_parser: The MCP argument parser (optional, used for showing help)
    """
    if args.mcp_command == "add":
        handle_mcp_add(args)
    elif args.mcp_command == "remove":
        handle_mcp_remove(args)
    elif args.mcp_command == "list":
        handle_mcp_list(args)
    elif args.mcp_command == "get":
        handle_mcp_get(args)
    elif args.mcp_command is None:
        # No subcommand provided, show help
        if mcp_parser:
            mcp_parser.print_help()
        else:
            # Fallback: recreate the parser to show help
            import argparse

            from openhands_cli.argparsers.mcp_parser import add_mcp_parser

            temp_parser = argparse.ArgumentParser()
            temp_subparsers = temp_parser.add_subparsers()
            mcp_parser = add_mcp_parser(temp_subparsers)
            mcp_parser.print_help()
        raise SystemExit(0)
    else:
        print_formatted_text(HTML("<red>Unknown MCP command</red>"))
        raise SystemExit(1)
