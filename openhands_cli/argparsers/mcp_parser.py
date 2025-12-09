"""Argument parser for MCP subcommand."""

import argparse


def add_mcp_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add MCP subcommand parser.

    Args:
        subparsers: The subparsers object to add the MCP parser to

    Returns:
        The MCP argument parser
    """
    description = """
Manage Model Context Protocol (MCP) server configurations.

MCP servers provide additional tools and context to OpenHands agents.
You can add HTTP/SSE servers with authentication or stdio-based local servers.

Examples:

  # Add an HTTP server with Bearer token authentication
  openhands mcp add my-api https://api.example.com/mcp \\
    --transport http \\
    --header "Authorization: Bearer your-token-here"

  # Add an HTTP server with API key authentication
  openhands mcp add weather-api https://weather.api.com \\
    --transport http \\
    --header "X-API-Key: your-api-key"

  # Add an HTTP server with multiple headers
  openhands mcp add secure-api https://api.example.com \\
    --transport http \\
    --header "Authorization: Bearer token123" \\
    --header "X-Client-ID: client456"

  # Add a local stdio server with environment variables
  openhands mcp add local-server python \\
    --transport stdio \\
    --env "API_KEY=secret123" \\
    --env "DATABASE_URL=postgresql://..." \\
    -- -m my_mcp_server --config config.json

  # Add an OAuth-based server (like Notion MCP)
  openhands mcp add notion-server https://mcp.notion.com/mcp \\
    --transport http \\
    --auth oauth

  # List all configured servers
  openhands mcp list

  # Get details for a specific server
  openhands mcp get my-api

  # Remove a server
  openhands mcp remove my-api
"""
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Manage Model Context Protocol (MCP) server configurations",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    add_parser.add_argument(
        "--auth",
        choices=["oauth"],
        help="Authentication method for the MCP server",
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
