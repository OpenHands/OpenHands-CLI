"""Utility functions for auth module."""

from rich.console import Console


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
