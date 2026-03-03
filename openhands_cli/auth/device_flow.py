"""OAuth 2.0 Device Flow client implementation for OpenHands CLI."""

import asyncio
import time
import webbrowser

from pydantic import BaseModel

from openhands_cli.auth.http_client import AuthHttpError, BaseHttpClient
from openhands_cli.auth.utils import console_print
from openhands_cli.theme import OPENHANDS_THEME


class DeviceFlowError(Exception):
    """Base exception for device flow errors."""

    pass


class DeviceAuthorizationResponse(BaseModel):
    """Response from the device authorization endpoint (RFC 8628)."""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class DeviceTokenResponse(BaseModel):
    """Successful token response from the device token endpoint (RFC 8628)."""

    access_token: str  # This will be the user's API key
    token_type: str = "Bearer"
    expires_in: int | None = None  # API keys may not have expiration


class DeviceTokenErrorResponse(BaseModel):
    """Error response from the device token endpoint (RFC 8628)."""

    error: str
    error_description: str | None = None
    interval: int | None = None  # Required for slow_down error


class DeviceFlowClient(BaseHttpClient):
    """OAuth 2.0 Device Flow client for CLI authentication."""

    def __init__(self, server_url: str) -> None:
        """Initialize the device flow client.

        Args:
            server_url: Base URL of the OpenHands server
        """
        super().__init__(server_url)

    async def start_device_flow(self) -> DeviceAuthorizationResponse:
        """Start the OAuth 2.0 Device Flow.

        Returns:
            DeviceAuthorizationResponse containing device_code, user_code,
            verification_uri, verification_uri_complete, expires_in, and interval

        Raises:
            DeviceFlowError: If the device flow initiation fails
        """
        try:
            response = await self.post("/oauth/device/authorize", json_data={})
            return DeviceAuthorizationResponse.model_validate(response.json())
        except AuthHttpError as e:
            raise DeviceFlowError(f"Failed to start device flow: {e}") from e
        except Exception as e:
            raise DeviceFlowError(
                f"Invalid response from device authorization endpoint: {e}"
            ) from e

    async def poll_for_token(
        self, device_code: str, interval: int, timeout: float = 600.0
    ) -> DeviceTokenResponse:
        """Poll for the API key after user authorization.

        Args:
            device_code: The device code from start_device_flow
            interval: Polling interval in seconds
            timeout: Maximum time to wait for authorization in seconds (default: 10 min)

        Returns:
            DeviceTokenResponse containing access_token (API key), token_type, etc.

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
                # Success - parse and validate the token response
                try:
                    return DeviceTokenResponse.model_validate(response.json())
                except Exception as e:
                    raise DeviceFlowError(
                        f"Invalid token response from server: {e}"
                    ) from e

            # Non-200: try to interpret the error using Pydantic model
            try:
                error_response = DeviceTokenErrorResponse.model_validate(
                    response.json()
                )
            except Exception:
                raise DeviceFlowError(
                    f"Unexpected response from server: {response.status_code}"
                )

            error = error_response.error
            description = error_response.error_description or ""

            if error == "authorization_pending":
                # User hasn't finished yet; just sleep and retry
                pass
            elif error == "slow_down":
                # Server asks us to poll less frequently
                # Use server-provided interval if available, otherwise double current
                if error_response.interval is not None:
                    interval = error_response.interval
                else:
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

    async def authenticate(self) -> DeviceTokenResponse:
        """Complete OAuth 2.0 Device Flow authentication.

        Returns:
            DeviceTokenResponse containing access_token (API key), token_type, etc.

        Raises:
            DeviceFlowError: If authentication fails
        """
        console_print(
            f"[{OPENHANDS_THEME.accent}]Starting OpenHands authentication..."
            f"[/{OPENHANDS_THEME.accent}]"
        )

        # Step 1: Start device flow
        try:
            auth_response = await self.start_device_flow()
        except DeviceFlowError as e:
            console_print(
                f"[{OPENHANDS_THEME.error}]Error: {e}[/{OPENHANDS_THEME.error}]"
            )
            raise

        # Step 2: Use verification_uri_complete if available, otherwise construct URL
        verification_url = auth_response.verification_uri_complete

        console_print(
            f"\n[{OPENHANDS_THEME.warning}]Opening your web browser for "
            f"authentication...[/{OPENHANDS_THEME.warning}]"
        )
        console_print(
            f"[{OPENHANDS_THEME.secondary}]URL: [bold]{verification_url}[/bold]"
            f"[/{OPENHANDS_THEME.secondary}]"
        )

        # Automatically open the browser
        try:
            webbrowser.open(verification_url)
            console_print(
                f"[{OPENHANDS_THEME.success}]✓ Browser "
                f"opened successfully[/{OPENHANDS_THEME.success}]"
            )
        except Exception as e:
            console_print(
                f"[{OPENHANDS_THEME.warning}]Could not open browser automatically: "
                f"{e}[/{OPENHANDS_THEME.warning}]"
            )
            console_print(
                f"[{OPENHANDS_THEME.secondary}]Please manually open: "
                f"[bold]{verification_url}[/bold][/{OPENHANDS_THEME.secondary}]"
            )

        console_print(
            f"[{OPENHANDS_THEME.secondary}]Follow the instructions in your browser "
            f"to complete authentication[/{OPENHANDS_THEME.secondary}]"
        )
        console_print(
            f"\n[{OPENHANDS_THEME.accent}]Waiting for authentication to complete..."
            f"[/{OPENHANDS_THEME.accent}]"
        )

        # Step 3: Poll for token using device_code and interval from auth_response
        try:
            token_response = await self.poll_for_token(
                auth_response.device_code, auth_response.interval
            )
            console_print(
                f"[{OPENHANDS_THEME.success}]✓ Authentication "
                f"successful![/{OPENHANDS_THEME.success}]"
            )
            return token_response
        except DeviceFlowError as e:
            console_print(
                f"[{OPENHANDS_THEME.error}]Error: {e}[/{OPENHANDS_THEME.error}]"
            )
            raise


async def authenticate_with_device_flow(server_url: str) -> DeviceTokenResponse:
    """Convenience function to authenticate using device flow.

    Args:
        server_url: OpenHands server URL

    Returns:
        DeviceTokenResponse containing access_token (API key), token_type, etc.

    Raises:
        DeviceFlowError: If authentication fails
    """
    client = DeviceFlowClient(server_url)
    return await client.authenticate()
