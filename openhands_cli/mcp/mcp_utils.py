"""MCP configuration management module.

This module provides functionality to manage MCP server configurations
similar to Claude's MCP command line interface.
"""

from pathlib import Path
from typing import Any, Literal, cast

from fastmcp.exceptions import ValidationError
from fastmcp.mcp_config import MCPConfig, RemoteMCPServer, StdioMCPServer
from pydantic import ValidationError as PydanticValidationError


def _get_mcp_config_path() -> Path:
    """Get the MCP configuration file path.

    This function dynamically resolves the path to ensure it works
    correctly when PERSISTENCE_DIR is patched in tests.
    """
    # Import the module and get the current value to support patching
    import openhands_cli.locations as locations

    return Path(locations.PERSISTENCE_DIR) / locations.MCP_CONFIG_FILE


class MCPConfigurationError(Exception):
    """Exception raised for MCP configuration errors."""

    pass


def _ensure_config_dir(config_path: Path) -> None:
    """Ensure the configuration directory exists.

    Args:
        config_path: Path to the configuration file
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)


def load_mcp_config() -> MCPConfig:
    """Load the MCP configuration from file.

    Returns:
        The MCPConfig object, or empty config if file doesn't exist.

    Raises:
        MCPConfigurationError: If the configuration file is invalid.
        ValidationError: If the configuration format is invalid.
    """
    config_path = _get_mcp_config_path()
    if not config_path.exists():
        # Return empty config with mcpServers structure
        return MCPConfig.from_dict({"mcpServers": {}})

    try:
        return MCPConfig.from_file(config_path)
    except (ValueError, PydanticValidationError) as e:
        # Re-raise as MCPConfigurationError for consistency
        raise MCPConfigurationError(f"Invalid MCP configuration file: {e}") from e
    except Exception as e:
        raise MCPConfigurationError(f"Error reading config file: {e}") from e


def save_mcp_config(config: MCPConfig) -> None:
    """Save the MCP configuration to file.

    Args:
        config: The MCPConfig object to save

    Raises:
        MCPConfigurationError: If the configuration cannot be saved.
    """
    try:
        config_path = _get_mcp_config_path()
        _ensure_config_dir(config_path)
        config.write_to_file(config_path)
    except Exception as e:
        raise MCPConfigurationError(f"Error saving config file: {e}") from e


def _parse_headers(headers: list[str] | None) -> dict[str, str]:
    """Parse header strings into a dictionary.

    Args:
        headers: List of header strings in format "key: value"

    Returns:
        Dictionary of headers

    Raises:
        MCPConfigurationError: If header format is invalid
    """
    if not headers:
        return {}

    parsed_headers = {}
    for header in headers:
        if ":" not in header:
            raise MCPConfigurationError(
                f"Invalid header format '{header}'. Expected 'key: value'"
            )
        key, value = header.split(":", 1)
        parsed_headers[key.strip()] = value.strip()
    return parsed_headers


def _parse_env_vars(env_vars: list[str] | None) -> dict[str, str]:
    """Parse environment variable strings into a dictionary.

    Args:
        env_vars: List of env var strings in format "KEY=value"

    Returns:
        Dictionary of environment variables

    Raises:
        MCPConfigurationError: If env var format is invalid
    """
    if not env_vars:
        return {}

    parsed_env = {}
    for env_var in env_vars:
        if "=" not in env_var:
            raise MCPConfigurationError(
                f"Invalid environment variable format '{env_var}'. Expected 'KEY=value'"
            )
        key, value = env_var.split("=", 1)
        parsed_env[key.strip()] = value.strip()
    return parsed_env


def add_server(
    name: str,
    transport: str,
    target: str,
    args: list[str] | None = None,
    headers: list[str] | None = None,
    env_vars: list[str] | None = None,
    auth: str | None = None,
) -> None:
    """Add a new MCP server configuration.

    Args:
        name: Name of the MCP server
        transport: Transport type (http, sse, stdio)
        target: URL for http/sse or command for stdio
        args: Additional arguments for stdio transport
        headers: HTTP headers for http/sse transports
        env_vars: Environment variables for stdio transport
        auth: Authentication method (e.g., "oauth")

    Raises:
        MCPConfigurationError: If configuration is invalid or server already exists
    """
    config = load_mcp_config()

    # Check if server already exists
    if name in config.mcpServers:
        raise MCPConfigurationError(f"MCP server '{name}' already exists")

    # Create the appropriate server object based on transport type
    if transport == "stdio":
        server = StdioMCPServer(
            command=target,
            args=args or [],
            env=_parse_env_vars(env_vars) if env_vars else {},
            transport="stdio",
        )
    elif transport in ["http", "sse"]:
        server = RemoteMCPServer(
            url=target,
            transport=cast(Literal["http", "sse"], transport),
            headers=_parse_headers(headers) if headers else {},
            auth=auth,
        )
    else:
        raise MCPConfigurationError(f"Invalid transport type: {transport}")

    # Add the server to the configuration
    config.add_server(name, server)
    save_mcp_config(config)

    # Validate the saved configuration by loading it (ensures compatibility)
    load_mcp_config()


def remove_server(name: str) -> None:
    """Remove an MCP server configuration.

    Args:
        name: Name of the MCP server to remove

    Raises:
        MCPConfigurationError: If server doesn't exist
    """
    config = load_mcp_config()

    # Check if server exists
    if name not in config.mcpServers:
        raise MCPConfigurationError(f"MCP server '{name}' not found")

    # Remove the server by creating a new config without it
    new_servers = {k: v for k, v in config.mcpServers.items() if k != name}
    new_config = MCPConfig.from_dict({"mcpServers": new_servers})
    save_mcp_config(new_config)

    # Validate the saved configuration by loading it (ensures it remains compatible)
    load_mcp_config()


def list_servers() -> dict[str, StdioMCPServer | RemoteMCPServer]:
    """List all configured MCP servers.

    Returns:
        Dictionary of server objects keyed by name
    """
    config = load_mcp_config()
    return config.mcpServers


def get_server(name: str) -> StdioMCPServer | RemoteMCPServer:
    """Get configuration for a specific MCP server.

    Args:
        name: Name of the MCP server

    Returns:
        Server object

    Raises:
        MCPConfigurationError: If server doesn't exist
    """
    config = load_mcp_config()
    servers = config.mcpServers

    if name not in servers:
        raise MCPConfigurationError(f"MCP server '{name}' not found")

    return servers[name]


def server_exists(name: str) -> bool:
    """Check if an MCP server configuration exists.

    Args:
        name: Name of the MCP server

    Returns:
        True if server exists, False otherwise
    """
    try:
        config = load_mcp_config()
        return name in config.mcpServers
    except (MCPConfigurationError, ValidationError):
        return False


def get_config_status() -> dict[str, Any]:
    """Get the status of the MCP configuration file.

    Returns:
        Dictionary with status information:
        {
            'exists': bool,
            'valid': bool,
            'servers': dict,
            'message': str
        }
    """
    config_path = _get_mcp_config_path()
    if not config_path.exists():
        return {
            "exists": False,
            "valid": False,
            "servers": {},
            "message": f"MCP configuration file not found at {config_path}",
        }

    try:
        config = load_mcp_config()
        servers = config.to_dict().get("mcpServers", {})
        return {
            "exists": True,
            "valid": True,
            "servers": servers,
            "message": f"Valid MCP configuration found with {len(servers)} server(s)",
        }
    except (MCPConfigurationError, ValidationError) as e:
        return {
            "exists": True,
            "valid": False,
            "servers": {},
            "message": f"Invalid MCP configuration file: {str(e)}",
        }
