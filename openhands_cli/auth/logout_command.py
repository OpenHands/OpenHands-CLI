"""Logout command implementation for OpenHands CLI."""

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.auth.token_storage import TokenStorage, TokenStorageError


def logout_command(server_url: str | None = None) -> bool:
    """Execute the logout command.

    Args:
        server_url: OpenHands server URL to log out from (None for all servers)

    Returns:
        True if logout was successful, False otherwise
    """
    try:
        token_storage = TokenStorage()

        if server_url:
            # Log out from specific server (simplified - we only support one server now)
            print_formatted_text(HTML(f"<cyan>Logging out from {server_url}...</cyan>"))

            if token_storage.remove_api_key():
                print_formatted_text(
                    HTML(f"<green>✓ Successfully logged out from {server_url}</green>")
                )
                return True
            else:
                print_formatted_text(
                    HTML(f"<yellow>You were not logged in to {server_url}</yellow>")
                )
                return True
        else:
            # Log out from all servers (simplified - we only have one API key)
            if not token_storage.has_api_key():
                print_formatted_text(
                    HTML("<yellow>You are not logged in to any servers.</yellow>")
                )
                return True

            print_formatted_text(HTML("<cyan>Logging out...</cyan>"))

            token_storage.remove_api_key()
            print_formatted_text(HTML("<green>✓ Successfully logged out</green>"))
            return True

    except TokenStorageError as e:
        print_formatted_text(HTML(f"<red>Failed to log out: {str(e)}</red>"))
        return False

    except Exception as e:
        print_formatted_text(
            HTML(f"<red>Unexpected error during logout: {str(e)}</red>")
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
