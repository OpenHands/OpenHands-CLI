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
                f"[{OPENHANDS_THEME.accent}]Logging out from OpenHands Cloud..."
                f"[/{OPENHANDS_THEME.accent}]"
            )

            was_logged_in = token_storage.remove_api_key()
            if was_logged_in:
                console_print(
                    f"[{OPENHANDS_THEME.success}]✓ Logged "
                    f"out of OpenHands Cloud[/{OPENHANDS_THEME.success}]"
                )
            else:
                console_print(
                    f"[{OPENHANDS_THEME.warning}]You were not logged in to "
                    f"OpenHands Cloud[/{OPENHANDS_THEME.warning}]"
                )

            return True

        # Logging out globally (no server specified)
        if not token_storage.has_api_key():
            console_print(
                f"[{OPENHANDS_THEME.warning}]You are not logged in to "
                f"OpenHands Cloud.[/{OPENHANDS_THEME.warning}]"
            )
            return True

        console_print(
            f"[{OPENHANDS_THEME.accent}]Logging out from OpenHands Cloud..."
            f"[/{OPENHANDS_THEME.accent}]"
        )
        token_storage.remove_api_key()
        console_print(
            f"[{OPENHANDS_THEME.success}]✓ Logged "
            f"out of OpenHands Cloud[/{OPENHANDS_THEME.success}]"
        )
        return True

    except Exception as e:
        console_print(
            f"[{OPENHANDS_THEME.error}]Unexpected error during logout: "
            f"{e}[/{OPENHANDS_THEME.error}]"
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
