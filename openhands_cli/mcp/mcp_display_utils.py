"""Utility functions for displaying MCP server information.

This module provides shared utilities for formatting MCP server
configuration details across different display contexts (CLI, TUI, etc.).
"""

from typing import Any

from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer


def normalize_server_object(
    server: StdioMCPServer | RemoteMCPServer | dict[str, Any],
) -> StdioMCPServer | RemoteMCPServer:
    """Convert dict format to FastMCP server object if needed.

    Handles both FastMCP objects and legacy dict format for compatibility.
    Detects server type based on transport field or presence of command vs url.

    Args:
        server: Server configuration as FastMCP object or dict

    Returns:
        FastMCP server object (StdioMCPServer or RemoteMCPServer)
    """
    if isinstance(server, dict):
        # Legacy dict format - convert to appropriate server object for processing
        # Detect server type based on transport field or presence of command vs url
        if server.get("transport") == "stdio" or (
            "command" in server and "url" not in server
        ):
            # Add default transport if missing for StdioMCPServer
            server_dict = server.copy()
            if "transport" not in server_dict:
                server_dict["transport"] = "stdio"
            return StdioMCPServer(**server_dict)
        else:
            # Add default transport if missing for RemoteMCPServer
            server_dict = server.copy()
            if "transport" not in server_dict:
                server_dict["transport"] = "http"
            return RemoteMCPServer(**server_dict)
    else:
        # Already a FastMCP object
        return server


def mask_sensitive_value(key: str, value: str) -> str:
    """Mask potentially sensitive values in configuration display.

    Args:
        key: Configuration key name
        value: Configuration value

    Returns:
        Masked value if sensitive, original value otherwise
    """
    sensitive_keys = {
        "authorization",
        "bearer",
        "token",
        "key",
        "secret",
        "password",
        "api_key",
        "apikey",
    }

    key_lower = key.lower()
    if any(sensitive in key_lower for sensitive in sensitive_keys):
        if len(value) <= 8:
            return "*" * len(value)
        else:
            return value[:4] + "*" * (len(value) - 8) + value[-4:]
    return value
