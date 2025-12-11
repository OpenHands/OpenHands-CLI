"""Logout command implementation for OpenHands CLI."""

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.auth.token_storage import TokenStorage


def _p(message: str) -> None:
    """Print formatted text via prompt_toolkit."""
    print_formatted_text(HTML(message))


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
            _p(f"<cyan>Logging out from {server_url}...</cyan>")

            was_logged_in = token_storage.remove_api_key()
            if was_logged_in:
                _p(f"<green>✓ Successfully logged out from {server_url}</green>")
            else:
                _p(f"<yellow>You were not logged in to {server_url}</yellow>")

            return True

        # Logging out globally (no server specified)
        if not token_storage.has_api_key():
            _p("<yellow>You are not logged in to any servers.</yellow>")
            return True

        _p("<cyan>Logging out...</cyan>")
        token_storage.remove_api_key()
        _p("<green>✓ Successfully logged out</green>")
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
