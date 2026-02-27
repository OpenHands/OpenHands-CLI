"""UI-agnostic login service for OpenHands CLI.

This module provides the core login flow logic that can be used by any UI
(console, TUI, etc.) by implementing the LoginProgressCallback protocol.
"""

import os
import webbrowser
from typing import Protocol, runtime_checkable


@runtime_checkable
class LoginProgressCallback(Protocol):
    """UI-agnostic interface for login progress updates.

    Implement this protocol to receive login progress updates in your UI.
    All methods have default no-op implementations, so you only need to
    implement the ones you care about.
    """

    def on_status(self, message: str) -> None:
        """Called when there's a status update to display."""
        ...

    def on_verification_url(self, url: str, user_code: str) -> None:
        """Called when the verification URL and user code are available."""
        ...

    def on_instructions(self, message: str) -> None:
        """Called when there are instructions to display."""
        ...

    def on_browser_opened(self, success: bool) -> None:
        """Called after attempting to open the browser."""
        ...

    def on_already_logged_in(self) -> None:
        """Called when user is already logged in with valid token."""
        ...

    def on_token_expired(self) -> None:
        """Called when existing token is invalid/expired."""
        ...

    def on_login_success(self) -> None:
        """Called when login completes successfully."""
        ...

    def on_settings_synced(self, success: bool, error: str | None = None) -> None:
        """Called after settings sync attempt."""
        ...

    def on_error(self, error: str) -> None:
        """Called when an error occurs."""
        ...


class NullLoginCallback:
    """No-op implementation of LoginProgressCallback for silent operation."""

    def on_status(self, message: str) -> None:
        pass

    def on_verification_url(self, url: str, user_code: str) -> None:
        pass

    def on_instructions(self, message: str) -> None:
        pass

    def on_browser_opened(self, success: bool) -> None:
        pass

    def on_already_logged_in(self) -> None:
        pass

    def on_token_expired(self) -> None:
        pass

    def on_login_success(self) -> None:
        pass

    def on_settings_synced(self, success: bool, error: str | None = None) -> None:
        pass

    def on_error(self, error: str) -> None:
        pass


async def run_login_flow(
    server_url: str | None = None,
    callback: LoginProgressCallback | None = None,
    skip_settings_sync: bool = False,
    open_browser: bool = True,
) -> bool:
    """Run the OAuth device flow login.

    This is the core login logic used by all UIs. It handles:
    1. Checking for existing valid token
    2. Handling invalid/expired tokens
    3. Running the device flow (start, show URL, poll)
    4. Storing the token
    5. Fetching user data and syncing settings

    Args:
        server_url: OpenHands server URL. Defaults to OPENHANDS_CLOUD_URL env var
                   or https://app.all-hands.dev
        callback: UI callback for progress updates. If None, uses NullLoginCallback.
        skip_settings_sync: If True, skip fetching user data after login.
        open_browser: If True, attempt to open the verification URL in browser.

    Returns:
        True if login was successful, False otherwise.
    """
    from openhands_cli.auth.api_client import (
        ApiClientError,
        fetch_user_data_after_oauth,
    )
    from openhands_cli.auth.device_flow import (
        DeviceFlowClient,
        DeviceFlowError,
    )
    from openhands_cli.auth.logout_command import logout_command
    from openhands_cli.auth.token_storage import TokenStorage
    from openhands_cli.auth.utils import is_token_valid

    # Use default server URL if not provided
    if server_url is None:
        server_url = os.getenv("OPENHANDS_CLOUD_URL", "https://app.all-hands.dev")

    # Use null callback if none provided
    if callback is None:
        callback = NullLoginCallback()

    token_storage = TokenStorage()

    # Step 1: Check for existing token and validate it
    existing_api_key = token_storage.get_api_key()

    if existing_api_key:
        if await is_token_valid(server_url, existing_api_key):
            # Already logged in with valid token
            callback.on_already_logged_in()
            callback.on_status("Already logged in. Syncing settings...")

            if not skip_settings_sync:
                try:
                    await fetch_user_data_after_oauth(server_url, existing_api_key)
                    callback.on_settings_synced(success=True)
                except ApiClientError as e:
                    callback.on_settings_synced(success=False, error=str(e))

            return True
        else:
            # Token is invalid/expired - logout first
            callback.on_token_expired()
            callback.on_status("Token expired. Logging out...")
            logout_command(server_url)
            # Clear the existing key reference since we just logged out
            existing_api_key = None

    # Step 2: Start device flow
    callback.on_status("Connecting to OpenHands Cloud...")
    client = DeviceFlowClient(server_url)

    try:
        # Step 3: Get device authorization
        auth_response = await client.start_device_flow()

        # Step 4: Show verification URL and user code
        verification_url = auth_response.verification_uri_complete
        user_code = auth_response.user_code
        callback.on_verification_url(verification_url, user_code)

        # Step 5: Open browser (optional)
        if open_browser:
            try:
                webbrowser.open(verification_url)
                callback.on_browser_opened(success=True)
                callback.on_status("Browser opened. Complete login in your browser.")
            except Exception:
                callback.on_browser_opened(success=False)
                callback.on_status("Please open the URL above in your browser.")
        else:
            callback.on_status("Please open the URL above in your browser.")

        # Step 6: Poll for token
        callback.on_instructions("Waiting for authentication to complete...")
        token_response = await client.poll_for_token(
            auth_response.device_code, auth_response.interval
        )

        # Step 7: Store the token
        token_storage.store_api_key(token_response.access_token)
        callback.on_login_success()
        callback.on_status("✓ Logged into OpenHands Cloud!")

        # Step 8: Fetch user data and sync settings
        if not skip_settings_sync:
            callback.on_instructions("Syncing settings...")
            try:
                await fetch_user_data_after_oauth(
                    server_url, token_response.access_token
                )
                callback.on_settings_synced(success=True)
                callback.on_instructions("✓ Settings synchronized!")
            except ApiClientError as e:
                callback.on_settings_synced(success=False, error=str(e))
                callback.on_instructions(f"Warning: Could not sync settings: {e}")

        return True

    except DeviceFlowError as e:
        callback.on_error(str(e))
        callback.on_status(f"Authentication failed: {e}")
        callback.on_instructions("Please try again.")
        return False
