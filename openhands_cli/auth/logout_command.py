"""Logout command implementation for OpenHands CLI."""

from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.auth.utils import _p


def logout_command(server_url: str | None = None) -> bool:
    """Execute the logout command.

    Args:
        server_url: OpenHands server URL to log out from (None for all servers)

    Returns:
        True if logout was successful, False otherwise
    """
    try:
        token_storage = TokenStorage()

        # Logging out from a specific server (conceptually; we only store one key)
        if server_url:
            _p("<cyan>Logging out from OpenHands Cloud...</cyan>")

            was_logged_in = token_storage.remove_api_key()
            if was_logged_in:
                _p("<green>✓ Logged out of OpenHands Cloud</green>")
            else:
                _p("<yellow>You were not logged in to OpenHands Cloud</yellow>")

            return True

        # Logging out globally (no server specified)
        if not token_storage.has_api_key():
            _p("<yellow>You are not logged in to OpenHands Cloud.</yellow>")
            return True

        _p("<cyan>Logging out from OpenHands Cloud...</cyan>")
        token_storage.remove_api_key()
        _p("<green>✓ Logged out of OpenHands Cloud</green>")
        return True

    except Exception as e:
        _p(f"<red>Unexpected error during logout: {e}</red>")
        return False


def run_logout_command(server_url: str | None = None) -> bool:
    """Run the logout command.

    Args:
        server_url: OpenHands server URL to log out from (None for all servers)

    Returns:
        True if logout was successful, False otherwise
    """
    return logout_command(server_url)
