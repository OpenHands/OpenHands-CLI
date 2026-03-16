"""Logout command implementation for OpenHands CLI."""

from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.auth.utils import console_print
from openhands_cli.theme import OPENHANDS_THEME


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
            console_print(
                "Logging out from OpenHands Cloud...", style=OPENHANDS_THEME.accent
            )

            was_logged_in = token_storage.remove_api_key()
            if was_logged_in:
                console_print(
                    "✓ Logged out of OpenHands Cloud", style=OPENHANDS_THEME.success
                )
            else:
                console_print(
                    "You were not logged in to OpenHands Cloud",
                    style=OPENHANDS_THEME.warning,
                )

            return True

        # Logging out globally (no server specified)
        if not token_storage.has_api_key():
            console_print(
                "You are not logged in to OpenHands Cloud.",
                style=OPENHANDS_THEME.warning,
            )
            return True

        console_print(
            "Logging out from OpenHands Cloud...", style=OPENHANDS_THEME.accent
        )
        token_storage.remove_api_key()
        console_print("✓ Logged out of OpenHands Cloud", style=OPENHANDS_THEME.success)
        return True

    except Exception as e:
        console_print(
            f"Unexpected error during logout: {e}", style=OPENHANDS_THEME.error
        )
        return False


def run_logout_command(server_url: str | None = None) -> bool:
    """Run the logout command.

    Args:
        server_url: OpenHands server URL to log out from (None for all servers)

    Returns:
        True if logout was successful, False otherwise
    """
    return logout_command(server_url)
