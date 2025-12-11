"""Utility functions for displaying MCP server information.

This module provides shared utilities for formatting MCP server
configuration details across different display contexts (CLI, TUI, etc.).
"""


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
