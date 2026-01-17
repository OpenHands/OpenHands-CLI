"""Utility functions for cloud module."""

from openhands_cli.auth.api_client import ApiClientError, OpenHandsApiClient
from openhands_cli.auth.utils import AuthenticationError, ensure_valid_auth


async def fetch_cloud_sandbox_id(server_url: str, conversation_id: str) -> str | None:
    """Fetch sandbox_id for a cloud conversation.

    Uses ensure_valid_auth to handle authentication.

    Args:
        server_url: The OpenHands Cloud server URL
        conversation_id: The conversation ID to look up

    Returns:
        sandbox_id if found, None otherwise
    """
    try:
        # Use ensure_valid_auth to get a valid API key (handles login if needed)
        api_key = await ensure_valid_auth(server_url)
    except AuthenticationError:
        return None

    client = OpenHandsApiClient(server_url, api_key)
    try:
        conversation_info = await client.get_conversation_info(conversation_id)
        if conversation_info:
            return conversation_info.get("sandbox_id")
        return None
    except ApiClientError:
        return None
