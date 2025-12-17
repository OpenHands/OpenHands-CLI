"""OAuth 2.0 Device Flow client implementation for OpenHands CLI."""

import asyncio
import json
import time
import webbrowser
from typing import Any

from openhands_cli.auth.http_client import AuthHttpError, BaseHttpClient
from openhands_cli.auth.utils import _p
from openhands_cli.theme import OPENHANDS_THEME


class DeviceFlowError(Exception):
    """Base exception for device flow errors."""

    pass


class DeviceFlowClient(BaseHttpClient):
    """OAuth 2.0 Device Flow client for CLI authentication."""

    def __init__(self, server_url: str):
        """Initialize the device flow client.

        Args:
            server_url: Base URL of the OpenHands server
        """
        super().__init__(server_url)

    async def start_device_flow(self) -> tuple[str, str, str, int]:
        """Start the OAuth 2.0 Device Flow.

        Returns:
            Tuple of (device_code, user_code, verification_uri, interval)

        Raises:
            DeviceFlowError: If the device flow initiation fails
        """
        try:
            response = await self.post("/oauth/device/authorize", json_data={})
            result = response.json()

            return (
                result["device_code"],
                result["user_code"],
                result["verification_uri"],
                result["interval"],
            )
        except (AuthHttpError, KeyError) as e:
            raise DeviceFlowError(f"Failed to start device flow: {e}") from e

    async def poll_for_token(
        self, device_code: str, interval: int, timeout: float = 600.0
    ) -> dict[str, Any]:
        """Poll for the API key after user authorization.

        Args:
            device_code: The device code from start_device_flow
            interval: Polling interval in seconds
            timeout: Maximum time to wait for authorization in seconds (default: 10 min)

        Returns:
            Dictionary containing access_token (API key), token_type, etc.

        Raises:
            DeviceFlowError: If polling fails or user denies access
        """
        data = {"device_code": device_code}
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = await self.post(
                    "/oauth/device/token",
                    form_data=data,
                    raise_for_status=False,
                )
            except AuthHttpError as e:
                raise DeviceFlowError(f"Network error during token polling: {e}") from e

            if response.status_code == 200:
                # Success
                return response.json()

            # Non-200: try to interpret the error
            try:
                error_data = response.json()
            except json.JSONDecodeError:
                raise DeviceFlowError(
                    f"Unexpected response from server: {response.status_code}"
                )

            error = error_data.get("error", "unknown_error")
            description = error_data.get("error_description", "")

            if error == "authorization_pending":
                # User hasn't finished yet; just sleep and retry
                pass
            elif error == "slow_down":
                # Server asks us to poll less frequently
                interval = min(interval * 2, 30)
            elif error == "expired_token":
                raise DeviceFlowError(
                    "Device code has expired. Please start a new login."
                )
            elif error == "access_denied":
                raise DeviceFlowError("User denied the authorization request.")
            else:
                raise DeviceFlowError(f"Authorization error: {error} - {description}")

            await asyncio.sleep(interval)

        raise DeviceFlowError(
            "Timeout waiting for user authorization. Please try again."
        )

    async def authenticate(self) -> dict[str, Any]:
        """Complete OAuth 2.0 Device Flow authentication.

        Returns:
            Dictionary containing access_token (API key), token_type, etc.

        Raises:
            DeviceFlowError: If authentication fails
        """
        _p(
            f"[{OPENHANDS_THEME.accent}]Starting OpenHands authentication..."
            f"[/{OPENHANDS_THEME.accent}]"
        )

        # Step 1: Start device flow
        try:
            (
                device_code,
                user_code,
                verification_uri,
                interval,
            ) = await self.start_device_flow()
        except DeviceFlowError as e:
            _p(f"[{OPENHANDS_THEME.error}]Error: {e}[/{OPENHANDS_THEME.error}]")
            raise

        # Step 2: Construct URL with user_code parameter and open browser
        verification_url = f"{verification_uri}?user_code={user_code}"

        _p(
            f"\n[{OPENHANDS_THEME.warning}]Opening your web browser for "
            f"authentication...[/{OPENHANDS_THEME.warning}]"
        )
        _p(
            f"[{OPENHANDS_THEME.secondary}]URL: [bold]{verification_url}[/bold]"
            f"[/{OPENHANDS_THEME.secondary}]"
        )

        # Automatically open the browser
        try:
            webbrowser.open(verification_url)
            _p(
                f"[{OPENHANDS_THEME.success}]✓ Browser "
                f"opened successfully[/{OPENHANDS_THEME.success}]"
            )
        except Exception as e:
            _p(
                f"[{OPENHANDS_THEME.warning}]Could not open browser automatically: "
                f"{e}[/{OPENHANDS_THEME.warning}]"
            )
            _p(
                f"[{OPENHANDS_THEME.secondary}]Please manually open: "
                f"[bold]{verification_url}[/bold][/{OPENHANDS_THEME.secondary}]"
            )

        _p(
            f"[{OPENHANDS_THEME.secondary}]Follow the instructions in your browser "
            f"to complete authentication[/{OPENHANDS_THEME.secondary}]"
        )
        _p(
            f"\n[{OPENHANDS_THEME.accent}]Waiting for authentication to complete..."
            f"[/{OPENHANDS_THEME.accent}]"
        )

        # Step 3: Poll for token
        try:
            tokens = await self.poll_for_token(device_code, interval)
            _p(
                f"[{OPENHANDS_THEME.success}]✓ Authentication "
                f"successful![/{OPENHANDS_THEME.success}]"
            )
            return tokens
        except DeviceFlowError as e:
            _p(f"[{OPENHANDS_THEME.error}]Error: {e}[/{OPENHANDS_THEME.error}]")
            raise


async def authenticate_with_device_flow(server_url: str) -> dict[str, Any]:
    """Convenience function to authenticate using device flow.

    Args:
        server_url: OpenHands server URL

    Returns:
        Dictionary containing authentication tokens

    Raises:
        DeviceFlowError: If authentication fails
    """
    client = DeviceFlowClient(server_url)
    return await client.authenticate()
