"""Argument parser for MCP subcommand."""

import argparse


def add_mcp_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add MCP subcommand parser.

    Args:
        subparsers: The subparsers object to add the MCP parser to

    Returns:
        The MCP argument parser
    """
    mcp_parser = subparsers.add_parser(
        "mcp", help="Manage Model Context Protocol (MCP) server configurations"
    )
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_command", help="MCP commands")

    # MCP add command
    add_parser = mcp_subparsers.add_parser("add", help="Add a new MCP server")
    add_parser.add_argument(
        "--transport",
        choices=["http", "sse", "stdio"],
        required=True,
        help="Transport type for the MCP server",
    )
    add_parser.add_argument("name", help="Name of the MCP server")
    add_parser.add_argument(
        "target", help="URL for http/sse transports or command for stdio transport"
    )
    add_parser.add_argument(
        "args",
        nargs="*",
        help="Additional arguments for stdio transport (after --)",
    )
    add_parser.add_argument(
        "--header",
        action="append",
        help="HTTP header for http/sse transports (format: 'key: value')",
    )
    add_parser.add_argument(
        "--env",
        action="append",
        help="Environment variable for stdio transport (format: KEY=value)",
    )

    # MCP list command
    mcp_subparsers.add_parser("list", help="List all configured MCP servers")

    # MCP get command
    get_parser = mcp_subparsers.add_parser(
        "get", help="Get details for a specific MCP server"
    )
    get_parser.add_argument("name", help="Name of the MCP server to get details for")

    # MCP remove command
    remove_parser = mcp_subparsers.add_parser("remove", help="Remove an MCP server")
    remove_parser.add_argument("name", help="Name of the MCP server to remove")

    return mcp_parser
