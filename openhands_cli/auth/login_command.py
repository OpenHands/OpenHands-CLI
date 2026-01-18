"""Login command implementation for OpenHands CLI."""

import asyncio
import html

from openhands_cli.auth.api_client import ApiClientError, fetch_user_data_after_oauth
from openhands_cli.auth.device_flow import (
    DeviceFlowError,
    authenticate_with_device_flow,
)
from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.auth.utils import _p, is_token_valid
from openhands_cli.theme import OPENHANDS_THEME


async def _fetch_user_data_with_context(
    server_url: str,
    api_key: str,
    already_logged_in: bool,
) -> None:
    """Fetch user data and print messages depending on login context."""

    # Initial context output
    if already_logged_in:
        _p(
            f"[{OPENHANDS_THEME.warning}]You are already logged in to "
            f"OpenHands Cloud.[/{OPENHANDS_THEME.warning}]"
        )
        _p(
            f"[{OPENHANDS_THEME.secondary}]Pulling latest settings from remote..."
            f"[/{OPENHANDS_THEME.secondary}]"
        )

    try:
        await fetch_user_data_after_oauth(server_url, api_key)

        # --- SUCCESS MESSAGES ---
        _p(
            f"\n[{OPENHANDS_THEME.success}]✓ Settings synchronized "
            f"successfully![/{OPENHANDS_THEME.success}]"
        )

    except ApiClientError as e:
        # --- FAILURE MESSAGES ---
        safe_error = html.escape(str(e))

        _p(
            f"\n[{OPENHANDS_THEME.warning}]Warning: "
            f"Could not fetch user data: {safe_error}[/{OPENHANDS_THEME.warning}]"
        )
        _p(
            f"[{OPENHANDS_THEME.secondary}]Please try: [bold]"
            f"{html.escape('openhands logout && openhands login')}"
            f"[/bold][/{OPENHANDS_THEME.secondary}]"
        )


async def login_command(server_url: str) -> bool:
    """Execute the login command.

    Args:
        server_url: OpenHands server URL to authenticate with

    Returns:
        True if login was successful, False otherwise
    """
    from openhands_cli.auth.logout_command import logout_command

    # Check for existing token and validate it immediately
    token_storage = TokenStorage()
    existing_api_key = token_storage.get_api_key()

    if existing_api_key and not await is_token_valid(server_url, existing_api_key):
        _p(
            f"[{OPENHANDS_THEME.warning}]Token is invalid or expired. "
            f"Logging out...[/{OPENHANDS_THEME.warning}]"
        )
        logout_command(server_url)

    # Proceed with normal login flow
    _p(
        f"[{OPENHANDS_THEME.accent}]Logging in to OpenHands Cloud..."
        f"[/{OPENHANDS_THEME.accent}]"
    )

    # Re-read token (may have been cleared by logout above)
    existing_api_key = token_storage.get_api_key()

    # If we already have a valid API key, just sync settings and exit
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
        _p(
            f"[{OPENHANDS_THEME.error}]Authentication failed: "
            f"{e}[/{OPENHANDS_THEME.error}]"
        )
        return False

    api_key = tokens.get("access_token")

    if not api_key:
        _p(
            f"\n[{OPENHANDS_THEME.warning}]Warning: "
            f"No access token found in OAuth response.[/{OPENHANDS_THEME.warning}]"
        )
        _p(
            f"[{OPENHANDS_THEME.secondary}]You can still use OpenHands CLI with "
            f"cloud features.[/{OPENHANDS_THEME.secondary}]"
        )
        # Authentication technically succeeded, even if we lack a token
        return True

    # Store the API key securely
    token_storage.store_api_key(api_key)

    _p(
        f"[{OPENHANDS_THEME.success}]✓ Logged "
        f"into OpenHands Cloud[/{OPENHANDS_THEME.success}]"
    )
    _p(
        f"[{OPENHANDS_THEME.secondary}]Your authentication "
        f"tokens have been stored securely.[/{OPENHANDS_THEME.secondary}]"
    )

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
        _p(
            f"\n[{OPENHANDS_THEME.warning}]Login cancelled by "
            f"user.[/{OPENHANDS_THEME.warning}]"
        )
        return False
