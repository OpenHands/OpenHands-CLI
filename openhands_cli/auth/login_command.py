"""Login command implementation for OpenHands CLI."""

import asyncio

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.auth.api_client import ApiClientError, fetch_user_data_after_oauth
from openhands_cli.auth.device_flow import (
    DeviceFlowError,
    authenticate_with_device_flow,
)
from openhands_cli.auth.token_storage import TokenStorage


def _p(message: str) -> None:
    """Print formatted text via prompt_toolkit."""
    print_formatted_text(HTML(message))


async def _fetch_user_data_with_context(
    server_url: str,
    api_key: str,
    already_logged_in: bool,
) -> None:
    """Fetch user data and print messages depending on login context."""

    # Initial context output
    if already_logged_in:
        _p("<yellow>You are already logged in to this server.</yellow>")
        _p("<white>Pulling latest settings from remote...</white>")

    try:
        await fetch_user_data_after_oauth(server_url, api_key)

        # --- SUCCESS MESSAGES ---
        if already_logged_in:
            _p("\n<green>✓ Settings synchronized successfully!</green>")
        else:
            _p("\n<white>You can now use OpenHands CLI with cloud features.</white>")

    except ApiClientError as e:
        # --- FAILURE MESSAGES ---
        _p(f"\n<yellow>Warning: Could not fetch user data: {e}</yellow>")


async def login_command(server_url: str) -> bool:
    """Execute the login command.

    Args:
        server_url: OpenHands server URL to authenticate with

    Returns:
        True if login was successful, False otherwise
    """
    _p(f"<cyan>Logging in to OpenHands at {server_url}...</cyan>")

    # First, try to read any existing token
    token_storage = TokenStorage()
    existing_api_key = token_storage.get_api_key()

    # If we already have an API key, just sync settings and exit
    if existing_api_key:
        await _fetch_user_data_with_context(
            server_url,
            existing_api_key,
            already_logged_in=True,
        )
        return True

    # No existing token: run device flow
    try:
        tokens = await authenticate_with_device_flow(server_url)
    except DeviceFlowError as e:
        _p(f"<red>Authentication failed: {e}</red>")
        return False

    api_key = tokens.get("access_token")

    if not api_key:
        _p("\n<yellow>Warning: No access token found in OAuth response.</yellow>")
        _p("<white>You can still use OpenHands CLI with cloud features.</white>")
        # Authentication technically succeeded, even if we lack a token
        return True

    # Store the API key securely
    token_storage.store_api_key(api_key)

    _p(f"<green>✓ Successfully logged in to {server_url}</green>")
    _p("<white>Your authentication tokens have been stored securely.</white>")

    # Fetch user data and configure local agent
    await _fetch_user_data_with_context(
        server_url,
        api_key,
        already_logged_in=False,
    )
    return True


def run_login_command(server_url: str) -> bool:
    """Run the login command synchronously.

    Args:
        server_url: OpenHands server URL to authenticate with

    Returns:
        True if login was successful, False otherwise
    """
    try:
        return asyncio.run(login_command(server_url))
    except KeyboardInterrupt:
        _p("\n<yellow>Login cancelled by user.</yellow>")
        return False
