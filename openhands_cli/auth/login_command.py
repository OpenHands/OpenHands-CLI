"""Login command implementation for OpenHands CLI."""

import asyncio
import html

from openhands_cli.auth.api_client import ApiClientError, fetch_user_data_after_oauth
from openhands_cli.auth.device_flow import (
    DeviceFlowError,
    authenticate_with_device_flow,
)
from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.auth.utils import _p
from openhands_cli.theme import OPENHANDS_THEME


async def _fetch_user_data_with_context(
    server_url: str,
    api_key: str,
    already_logged_in: bool,
    sync_settings: bool | None = None,
    silent: bool = False,
) -> None:
    """Fetch user data and print messages depending on login context.

    Args:
        server_url: OpenHands server URL
        api_key: API key for authentication
        already_logged_in: Whether user was already logged in
        sync_settings: If True, always sync settings. If False, never sync.
                      If None, prompt user for consent.
        silent: If True, suppress output messages
    """

    # Initial context output
    if not silent:
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
        await fetch_user_data_after_oauth(
            server_url, api_key, sync_settings=sync_settings, silent=silent
        )

        # --- SUCCESS MESSAGES ---
        if not silent:
            _p(
                f"\n[{OPENHANDS_THEME.success}]✓ Settings synchronized "
                f"successfully![/{OPENHANDS_THEME.success}]"
            )

    except ApiClientError as e:
        # --- FAILURE MESSAGES ---
        if not silent:
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


async def login_command(
    server_url: str,
    sync_settings: bool | None = None,
    silent: bool = False,
) -> bool:
    """Execute the login command.

    Args:
        server_url: OpenHands server URL to authenticate with
        sync_settings: If True, always sync settings without prompting.
                      If False, skip settings sync.
                      If None (default), prompt user for consent.
        silent: If True, suppress output messages (for TUI use)

    Returns:
        True if login was successful, False otherwise
    """
    if not silent:
        _p(
            f"[{OPENHANDS_THEME.accent}]Logging in to OpenHands Cloud..."
            f"[/{OPENHANDS_THEME.accent}]"
        )

    # First, try to read any existing token
    token_storage = TokenStorage()
    existing_api_key = token_storage.get_api_key()

    # If we already have an API key, just sync settings and exit
    if existing_api_key:
        await _fetch_user_data_with_context(
            server_url,
            existing_api_key,
            already_logged_in=True,
            sync_settings=sync_settings,
            silent=silent,
        )
        return True

    # No existing token: run device flow
    try:
        tokens = await authenticate_with_device_flow(server_url)
    except DeviceFlowError as e:
        if not silent:
            _p(
                f"[{OPENHANDS_THEME.error}]Authentication failed: "
                f"{e}[/{OPENHANDS_THEME.error}]"
            )
        return False

    api_key = tokens.get("access_token")

    if not api_key:
        if not silent:
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

    if not silent:
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
        sync_settings=sync_settings,
        silent=silent,
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
