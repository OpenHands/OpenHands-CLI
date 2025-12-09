"""MCP configuration management module.

This module provides functionality to manage MCP server configurations
similar to Claude's MCP command line interface.
"""

import json
from pathlib import Path
from typing import Any

from openhands_cli.locations import MCP_CONFIG_FILE, PERSISTENCE_DIR


class MCPConfigurationError(Exception):
    """Exception raised for MCP configuration errors."""

    pass


def _get_config_path(config_path: str | None = None) -> Path:
    """Get the path to the MCP configuration file.

    Args:
        config_path: Optional custom path to the MCP config file.
                    If None, uses the default location.

    Returns:
        Path to the configuration file
    """
    if config_path:
        return Path(config_path)
    else:
        return Path(PERSISTENCE_DIR) / MCP_CONFIG_FILE


def _ensure_config_dir(config_path: Path) -> None:
    """Ensure the configuration directory exists.

    Args:
        config_path: Path to the configuration file
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)


def _load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load the MCP configuration from file.

    Args:
        config_path: Optional custom path to the MCP config file

    Returns:
        The configuration dictionary, or empty dict if file doesn't exist.

    Raises:
        MCPConfigurationError: If the configuration file is invalid.
    """
    path = _get_config_path(config_path)
    
    if not path.exists():
        return {"mcpServers": {}}

    try:
        with open(path) as f:
            config = json.load(f)
            # Ensure mcpServers key exists
            if "mcpServers" not in config:
                config["mcpServers"] = {}
            return config
    except json.JSONDecodeError as e:
        raise MCPConfigurationError(f"Invalid JSON in config file: {e}") from e
    except Exception as e:
        raise MCPConfigurationError(f"Error reading config file: {e}") from e


def _save_config(config: dict[str, Any], config_path: str | None = None) -> None:
    """Save the MCP configuration to file.

    Args:
        config: The configuration dictionary to save
        config_path: Optional custom path to the MCP config file

    Raises:
        MCPConfigurationError: If the configuration cannot be saved.
    """
    path = _get_config_path(config_path)
    
    try:
        _ensure_config_dir(path)
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
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
                f"Invalid environment variable format '{env_var}'. "
                "Expected 'KEY=value'"
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
    config_path: str | None = None,
) -> None:
    """Add a new MCP server configuration.

    Args:
        name: Name of the MCP server
        transport: Transport type (http, sse, stdio)
        target: URL for http/sse or command for stdio
        args: Additional arguments for stdio transport
        headers: HTTP headers for http/sse transports
        env_vars: Environment variables for stdio transport
        config_path: Optional custom path to the MCP config file

    Raises:
        MCPConfigurationError: If configuration is invalid or server already exists
    """
    config = _load_config(config_path)

    if name in config["mcpServers"]:
        raise MCPConfigurationError(f"MCP server '{name}' already exists")

    server_config: dict[str, Any] = {"transport": transport}

    if transport in ["http", "sse"]:
        server_config["url"] = target
        if headers:
            server_config["headers"] = _parse_headers(headers)
    elif transport == "stdio":
        server_config["command"] = target
        if args:
            server_config["args"] = args
        if env_vars:
            server_config["env"] = _parse_env_vars(env_vars)
    else:
        raise MCPConfigurationError(f"Invalid transport type: {transport}")

    config["mcpServers"][name] = server_config
    _save_config(config, config_path)


def remove_server(name: str, config_path: str | None = None) -> None:
    """Remove an MCP server configuration.

    Args:
        name: Name of the MCP server to remove
        config_path: Optional custom path to the MCP config file

    Raises:
        MCPConfigurationError: If server doesn't exist
    """
    config = _load_config(config_path)

    if name not in config["mcpServers"]:
        raise MCPConfigurationError(f"MCP server '{name}' not found")

    del config["mcpServers"][name]
    _save_config(config, config_path)


def list_servers(config_path: str | None = None) -> dict[str, dict[str, Any]]:
    """List all configured MCP servers.

    Args:
        config_path: Optional custom path to the MCP config file

    Returns:
        Dictionary of server configurations keyed by name
    """
    config = _load_config(config_path)
    return config["mcpServers"]


def get_server(name: str, config_path: str | None = None) -> dict[str, Any]:
    """Get configuration for a specific MCP server.

    Args:
        name: Name of the MCP server
        config_path: Optional custom path to the MCP config file

    Returns:
        Server configuration dictionary

    Raises:
        MCPConfigurationError: If server doesn't exist
    """
    config = _load_config(config_path)

    if name not in config["mcpServers"]:
        raise MCPConfigurationError(f"MCP server '{name}' not found")

    return config["mcpServers"][name]


def server_exists(name: str, config_path: str | None = None) -> bool:
    """Check if an MCP server configuration exists.

    Args:
        name: Name of the MCP server
        config_path: Optional custom path to the MCP config file

    Returns:
        True if server exists, False otherwise
    """
    try:
        config = _load_config(config_path)
        return name in config["mcpServers"]
    except MCPConfigurationError:
        return False
