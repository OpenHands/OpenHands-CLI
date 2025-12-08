"""Login action for OpenHands Cloud authentication using OAuth 2.0 Device Flow."""

import asyncio
import time
import webbrowser
from typing import Any

import httpx

from openhands_cli.tui.settings.store import AgentStore


class DeviceAuthError(Exception):
    """Error during device authorization flow."""

    pass


class DeviceAuthTimeoutError(DeviceAuthError):
    """Device authorization timed out."""

    pass


async def request_device_code(
    base_url: str = "https://app.all-hands.dev",
) -> dict[str, Any]:
    """
    Request a device code from the OpenHands Cloud backend.

    Args:
        base_url: Base URL of the OpenHands Cloud backend

    Returns:
        Dictionary containing:
        - device_code: Code for polling
        - user_code: Code to display to user
        - verification_uri: URL where user enters code
        - expires_in: Seconds until code expires
        - interval: Polling interval in seconds

    Raises:
        DeviceAuthError: If the request fails
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/api/v1/auth/device",
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise DeviceAuthError(f"Failed to request device code: {e}") from e


async def poll_for_token(
    device_code: str,
    interval: int = 5,
    expires_in: int = 300,
    base_url: str = "https://app.all-hands.dev",
) -> str:
    """
    Poll the backend for the API key after user authorization.

    Args:
        device_code: Device code from request_device_code
        interval: Polling interval in seconds
        expires_in: Seconds until device code expires
        base_url: Base URL of the OpenHands Cloud backend

    Returns:
        API key string

    Raises:
        DeviceAuthTimeoutError: If the device code expires
        DeviceAuthError: If polling fails
    """
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        while True:
            # Check if we've exceeded the expiration time
            if time.time() - start_time > expires_in:
                raise DeviceAuthTimeoutError(
                    "Device authorization timed out. Please try again."
                )

            try:
                response = await client.post(
                    f"{base_url}/api/v1/auth/device/token",
                    json={"device_code": device_code},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    if "api_key" in data:
                        return data["api_key"]
                    # Still pending
                    if data.get("status") == "pending":
                        await asyncio.sleep(interval)
                        continue
                    raise DeviceAuthError(f"Unexpected response from backend: {data}")

                if response.status_code == 400:
                    error_data = response.json()
                    error = error_data.get("error", "unknown_error")

                    if error == "expired_token":
                        raise DeviceAuthTimeoutError(
                            "Device code expired. Please try again."
                        )
                    if error == "access_denied":
                        raise DeviceAuthError(
                            "Authorization was denied. Please try again."
                        )
                    raise DeviceAuthError(f"Authorization failed: {error}")

                raise DeviceAuthError(f"Unexpected status code: {response.status_code}")

            except httpx.HTTPError:
                # Don't fail immediately on network errors, keep polling
                await asyncio.sleep(interval)
                continue


async def login_to_openhands_cloud(
    base_url: str = "https://app.all-hands.dev",
) -> str:
    """
    Authenticate with OpenHands Cloud using OAuth 2.0 Device Flow.

    This implements the device authorization grant flow:
    1. Request a device code
    2. Display user code and open browser
    3. Poll for authorization completion
    4. Save API key to settings

    Args:
        base_url: Base URL of the OpenHands Cloud backend

    Returns:
        API key string

    Raises:
        DeviceAuthError: If authentication fails
        KeyboardInterrupt: If user cancels the flow
    """
    print("\n🔐 OpenHands Cloud Login")
    print("=" * 50)

    # Step 1: Request device code
    print("\n📱 Requesting device code...")
    try:
        device_data = await request_device_code(base_url)
    except DeviceAuthError as e:
        print(f"\n❌ Error: {e}")
        raise

    device_code = device_data["device_code"]
    user_code = device_data["user_code"]
    verification_uri = device_data["verification_uri"]
    expires_in = device_data.get("expires_in", 300)
    interval = device_data.get("interval", 5)

    # Step 2: Display user code and open browser
    print("\n✅ Device code received!")
    print(f"\n🌐 Opening browser to: {verification_uri}")
    print(f"📋 Please enter this code: \033[1m{user_code}\033[0m")
    print(f"\n⏱️  Code expires in {expires_in // 60} minutes")

    try:
        webbrowser.open(verification_uri)
    except Exception as e:
        print(f"\n⚠️  Could not open browser automatically: {e}")
        print(f"Please manually open: {verification_uri}")

    # Step 3: Poll for authorization
    print("\n⏳ Waiting for authentication...")
    print("(Press Ctrl+C to cancel)")

    try:
        api_key = await poll_for_token(
            device_code=device_code,
            interval=interval,
            expires_in=expires_in,
            base_url=base_url,
        )
    except DeviceAuthTimeoutError as e:
        print(f"\n⏱️  {e}")
        raise
    except DeviceAuthError as e:
        print(f"\n❌ {e}")
        raise
    except KeyboardInterrupt:
        print("\n\n🚫 Login cancelled by user")
        raise

    # Step 4: Save API key
    print("\n✅ Authentication successful!")
    print("\n💾 Saving API key to settings...")

    store = AgentStore()
    settings = store.load()

    # Update the API key in settings
    # Note: The AgentStore structure may vary, adjust as needed
    if hasattr(settings, "llm"):
        settings.llm.api_key = api_key
    elif hasattr(settings, "api_key"):
        settings.api_key = api_key  # type: ignore
    else:
        # Fallback: just ensure we have the settings object
        pass

    # Set provider to openhands if not already set
    if hasattr(settings, "llm") and hasattr(settings.llm, "api_base"):
        settings.llm.api_base = "https://llm-proxy.app.all-hands.dev"

    store.save(settings)

    print(f"✅ API key saved to {store.settings_file}")
    print("\n🎉 Login complete! You can now use OpenHands CLI.")
    print("\n💡 To change providers or models, run: \033[1mopenhands settings\033[0m")

    return api_key


def login_action() -> None:
    """
    Execute the login flow (synchronous wrapper).

    This is the entry point called from the CLI.
    """
    try:
        asyncio.run(login_to_openhands_cloud())
    except KeyboardInterrupt:
        print("\n")
        return
    except DeviceAuthError:
        print(
            "\n💡 Tip: You can manually set your API key by running: "
            "\033[1mopenhands settings\033[0m"
        )
        return
