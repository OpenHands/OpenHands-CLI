"""Utility functions for fetching user data using stored authentication."""

import asyncio
from typing import Any

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.auth.api_client import ApiClientError, fetch_user_data_after_oauth
from openhands_cli.auth.token_storage import get_token_storage


async def get_user_data_for_server(server_url: str) -> dict[str, Any] | None:
    """Get user data for a specific server using stored authentication.

    Args:
        server_url: OpenHands server URL

    Returns:
        Dictionary containing user data if successful, None otherwise
    """
    token_storage = get_token_storage()
    tokens = token_storage.get_tokens(server_url)

    if not tokens:
        print_formatted_text(
            HTML(f"<red>No authentication tokens found for {server_url}</red>")
        )
        print_formatted_text(HTML("<white>Please run 'openhands login' first.</white>"))
        return None

    api_key = tokens.get("access_token")
    if not api_key:
        print_formatted_text(HTML(f"<red>No access token found for {server_url}</red>"))
        print_formatted_text(HTML("<white>Please run 'openhands login' again.</white>"))
        return None

    try:
        return await fetch_user_data_after_oauth(server_url, api_key)
    except ApiClientError as e:
        print_formatted_text(HTML(f"<red>Failed to fetch user data: {str(e)}</red>"))
        return None


def run_get_user_data_for_server(server_url: str) -> dict[str, Any] | None:
    """Run get_user_data_for_server synchronously.

    Args:
        server_url: OpenHands server URL

    Returns:
        Dictionary containing user data if successful, None otherwise
    """
    try:
        return asyncio.run(get_user_data_for_server(server_url))
    except KeyboardInterrupt:
        print_formatted_text(HTML("\n<yellow>Operation cancelled by user.</yellow>"))
        return None


async def get_llm_api_key_for_server(server_url: str) -> str | None:
    """Get just the LLM API key for a specific server.

    Args:
        server_url: OpenHands server URL

    Returns:
        LLM API key if available, None otherwise
    """
    user_data = await get_user_data_for_server(server_url)
    if user_data:
        return user_data.get("llm_api_key")
    return None


def run_get_llm_api_key_for_server(server_url: str) -> str | None:
    """Run get_llm_api_key_for_server synchronously.

    Args:
        server_url: OpenHands server URL

    Returns:
        LLM API key if available, None otherwise
    """
    try:
        return asyncio.run(get_llm_api_key_for_server(server_url))
    except KeyboardInterrupt:
        print_formatted_text(HTML("\n<yellow>Operation cancelled by user.</yellow>"))
        return None
