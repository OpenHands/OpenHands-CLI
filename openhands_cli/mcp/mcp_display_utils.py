"""Utility functions for displaying MCP server information.

This module provides shared utilities for extracting and formatting MCP server
configuration details across different display contexts (CLI, TUI, etc.).
"""

from typing import Any


def extract_server_info(server_spec: dict[str, Any]) -> dict[str, Any]:
    """Extract standardized server information from server configuration.
    
    Args:
        server_spec: Server configuration dictionary
        
    Returns:
        Dictionary with standardized server information:
        {
            'transport_type': 'stdio' | 'http' | 'sse' | 'unknown',
            'command': str | None,
            'args': list[str] | None,
            'url': str | None,
            'auth': str | None,
            'headers': dict | None,
            'env': dict | None
        }
    """
    if not isinstance(server_spec, dict):
        return {
            'transport_type': 'unknown',
            'command': None,
            'args': None,
            'url': None,
            'auth': None,
            'headers': None,
            'env': None
        }
    
    # Determine transport type
    transport = server_spec.get("transport", "unknown")
    if transport == "unknown":
        # Fallback detection based on presence of fields
        if "command" in server_spec:
            transport = "stdio"
        elif "url" in server_spec:
            transport = "http"  # Default for URL-based
    
    return {
        'transport_type': transport,
        'command': server_spec.get("command"),
        'args': server_spec.get("args"),
        'url': server_spec.get("url"),
        'auth': server_spec.get("auth"),
        'headers': server_spec.get("headers"),
        'env': server_spec.get("env")
    }


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


def format_command_details(command: str | None, args: list[str] | None) -> str:
    """Format command and arguments into a display string.
    
    Args:
        command: Command string
        args: List of arguments
        
    Returns:
        Formatted command string
    """
    if not command:
        command = ""
    
    if args:
        args_str = " ".join(args)
        return f"{command} {args_str}".strip()
    
    return command


def format_server_type_label(transport_type: str) -> str:
    """Get user-friendly label for transport type.
    
    Args:
        transport_type: Transport type string
        
    Returns:
        User-friendly label
    """
    type_labels = {
        'stdio': 'Command-based',
        'http': 'URL-based',
        'sse': 'URL-based',
        'unknown': 'Unknown'
    }
    
    return type_labels.get(transport_type, 'Unknown')


def is_command_based_server(server_spec: dict[str, Any]) -> bool:
    """Check if server is command-based (stdio transport).
    
    Args:
        server_spec: Server configuration dictionary
        
    Returns:
        True if command-based, False otherwise
    """
    info = extract_server_info(server_spec)
    return info['transport_type'] == 'stdio'


def is_url_based_server(server_spec: dict[str, Any]) -> bool:
    """Check if server is URL-based (http/sse transport).
    
    Args:
        server_spec: Server configuration dictionary
        
    Returns:
        True if URL-based, False otherwise
    """
    info = extract_server_info(server_spec)
    return info['transport_type'] in ['http', 'sse']