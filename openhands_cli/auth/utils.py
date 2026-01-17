"""Utility functions for auth module."""

from rich.console import Console

from openhands_cli.theme import OPENHANDS_THEME


# Create a console instance for printing
_console = Console()


def _p(message: str) -> None:
    """Unified formatted print helper using rich console."""
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
            _console.print(
                f"[{OPENHANDS_THEME.warning}]You are not logged in to OpenHands Cloud."
                f"[/{OPENHANDS_THEME.warning}]"
            )
        else:
            _console.print(
                f"[{OPENHANDS_THEME.warning}]Your connection with OpenHands Cloud "
                f"has expired.[/{OPENHANDS_THEME.warning}]"
            )

        _console.print(
            f"[{OPENHANDS_THEME.accent}]Starting login...[/{OPENHANDS_THEME.accent}]"
        )
        success = await login_command(server_url)
        if not success:
            raise AuthenticationError("Login failed")

        # Re-read the API key after login
        api_key = store.get_api_key()
        if not api_key:
            raise AuthenticationError("No API key after login")

    return api_key
