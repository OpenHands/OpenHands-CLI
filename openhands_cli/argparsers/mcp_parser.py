"""Argument parser for MCP subcommand."""

import argparse
import sys
from typing import NoReturn


class MCPArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser for MCP commands that shows full help on errors."""

    def error(self, message: str) -> NoReturn:
        """Override error method to show full help instead of just usage."""
        # Print the full help including examples
        self.print_help(sys.stderr)
        # Print a separator and the specific error message
        print(f"\nError: {message}", file=sys.stderr)
        sys.exit(2)


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
  openhands mcp add my-api --transport http \\
    --header "Authorization: Bearer your-token-here" \\
    https://api.example.com/mcp

  # Add an HTTP server with API key authentication
  openhands mcp add weather-api --transport http \\
    --header "X-API-Key: your-api-key" \\
    https://weather.api.com

  # Add an HTTP server with multiple headers
  openhands mcp add secure-api --transport http \\
    --header "Authorization: Bearer token123" \\
    --header "X-Client-ID: client456" \\
    https://api.example.com

  # Add a local stdio server with environment variables
  openhands mcp add local-server --transport stdio \\
    --env "API_KEY=secret123" \\
    --env "DATABASE_URL=postgresql://..." \\
    python -- -m my_mcp_server --config config.json

  # Add an OAuth-based server (like Notion MCP)
  openhands mcp add notion-server --transport http \\
    --auth oauth \\
    https://mcp.notion.com/mcp

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
    mcp_subparsers = mcp_parser.add_subparsers(
        dest="mcp_command",
        help="MCP commands",
        required=True,
        parser_class=MCPArgumentParser,
    )

    # MCP add command
    add_description = """
Add a new MCP server configuration.

Examples:

  # Add an HTTP server with Bearer token authentication
  openhands mcp add my-api --transport http \\
    --header "Authorization: Bearer your-token-here" \\
    https://api.example.com/mcp

  # Add an HTTP server with API key authentication
  openhands mcp add weather-api --transport http \\
    --header "X-API-Key: your-api-key" \\
    https://weather.api.com

  # Add an HTTP server with multiple headers
  openhands mcp add secure-api --transport http \\
    --header "Authorization: Bearer token123" \\
    --header "X-Client-ID: client456" \\
    https://api.example.com

  # Add a local stdio server with environment variables
  openhands mcp add local-server --transport stdio \\
    --env "API_KEY=secret123" \\
    --env "DATABASE_URL=postgresql://..." \\
    python -- -m my_mcp_server --config config.json

  # Add an OAuth-based server (like Notion MCP)
  openhands mcp add notion-server --transport http \\
    --auth oauth \\
    https://mcp.notion.com/mcp
"""
    add_parser = mcp_subparsers.add_parser(
        "add",
        help="Add a new MCP server",
        description=add_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Optional arguments first
    add_parser.add_argument(
        "--transport",
        choices=["http", "sse", "stdio"],
        required=True,
        help="Transport type for the MCP server",
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

    # Positional arguments after optional arguments
    add_parser.add_argument("name", help="Name of the MCP server")
    add_parser.add_argument(
        "target", help="URL for http/sse transports or command for stdio transport"
    )
    add_parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Additional arguments for stdio transport (after --)",
    )

    # MCP list command
    list_description = """
List all configured MCP servers.

Examples:

  # List all configured servers
  openhands mcp list
"""
    mcp_subparsers.add_parser(
        "list",
        help="List all configured MCP servers",
        description=list_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # MCP get command
    get_description = """
Get details for a specific MCP server.

Examples:

  # Get details for a specific server
  openhands mcp get my-api
"""
    get_parser = mcp_subparsers.add_parser(
        "get",
        help="Get details for a specific MCP server",
        description=get_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    get_parser.add_argument("name", help="Name of the MCP server to get details for")

    # MCP remove command
    remove_description = """
Remove an MCP server configuration.

Examples:

  # Remove a server
  openhands mcp remove my-api
"""
    remove_parser = mcp_subparsers.add_parser(
        "remove",
        help="Remove an MCP server",
        description=remove_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    remove_parser.add_argument("name", help="Name of the MCP server to remove")

    return mcp_parser
