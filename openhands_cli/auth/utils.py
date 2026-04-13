"""Utility functions for auth module."""

from rich.console import Console

from openhands_cli.theme import OPENHANDS_THEME


__all__ = [
    "AuthenticationError",
    "console_print",
    "ensure_valid_auth",
    "is_token_valid",
]

# Create a console instance for printing
_console = Console()


def console_print(message: str, *, style: str | None = None) -> None:
    """Unified formatted print helper using rich console.

    Args:
        message: Text to print (may contain Rich markup).
        style: Optional OPENHANDS_THEME style name.  When given, the message
            is automatically wrapped in ``[{style}]…[/{style}]`` tags so
            callers don't have to repeat the verbose markup pattern.
    """
    if style:
        _console.print(f"[{style}]{message}[/{style}]")
    else:
        _console.print(message)


async def is_token_valid(server_url: str, api_key: str) -> bool:
    """Validate token; return False for auth failures, raise for other errors."""
    # Import here to avoid circular import with api_client
    from openhands_cli.auth.api_client import OpenHandsApiClient, UnauthenticatedError

    client = OpenHandsApiClient(server_url, api_key)
    try:
        await client.get_user_info()
        return True
    except UnauthenticatedError:
        return False


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""


async def ensure_valid_auth(server_url: str) -> str:
    """Ensure valid authentication, running login if needed.

    Args:
        server_url: OpenHands server URL to authenticate with

    Returns:
        Valid API key

    Raises:
        AuthenticationError: If login fails or no API key after login
    """
    from openhands_cli.auth.login_command import login_command
    from openhands_cli.auth.token_storage import TokenStorage

    store = TokenStorage()
    api_key = store.get_api_key()

    # If no API key or token is invalid, run login
    if not api_key or not await is_token_valid(server_url, api_key):
        if not api_key:
            console_print(
                "You are not logged in to OpenHands Cloud.",
                style=OPENHANDS_THEME.warning,
            )
        else:
            console_print(
                "Your connection with OpenHands Cloud has expired.",
                style=OPENHANDS_THEME.warning,
            )

        console_print("Starting login...", style=OPENHANDS_THEME.accent)
        success = await login_command(server_url)
        if not success:
            raise AuthenticationError("Login failed")

        # Re-read the API key after login
        api_key = store.get_api_key()
        if not api_key:
            raise AuthenticationError("No API key after login")

    return api_key
