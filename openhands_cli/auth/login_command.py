"""Login command implementation for OpenHands CLI."""

import asyncio

from openhands_cli.auth.login_service import StatusType, run_login_flow
from openhands_cli.auth.utils import console_print
from openhands_cli.theme import OPENHANDS_THEME


class ConsoleLoginCallback:
    """Console-based implementation of LoginProgressCallback.

    Displays login progress using Rich console output.
    """

    def on_status(
        self, message: str, status_type: StatusType = StatusType.INFO
    ) -> None:
        """Display status message with appropriate styling based on status type.

        Args:
            message: The status message to display
            status_type: The type of status for styling (INFO, SUCCESS, WARNING, ERROR)
        """
        style_map = {
            StatusType.INFO: OPENHANDS_THEME.accent,
            StatusType.SUCCESS: OPENHANDS_THEME.success,
            StatusType.WARNING: OPENHANDS_THEME.warning,
            StatusType.ERROR: OPENHANDS_THEME.error,
        }
        style = style_map.get(status_type, OPENHANDS_THEME.accent)
        console_print(f"[{style}]{message}[/{style}]")

    def on_verification_url(self, url: str, user_code: str) -> None:
        """Display verification URL and user code."""
        console_print(
            f"\n[{OPENHANDS_THEME.warning}]Opening your web browser for "
            f"authentication...[/{OPENHANDS_THEME.warning}]"
        )
        console_print(
            f"[{OPENHANDS_THEME.secondary}]URL: [bold]{url}[/bold]"
            f"[/{OPENHANDS_THEME.secondary}]"
        )
        console_print(
            f"[{OPENHANDS_THEME.secondary}]Your code: [bold]{user_code}[/bold]"
            f"[/{OPENHANDS_THEME.secondary}]"
        )

    def on_instructions(
        self, message: str, status_type: StatusType = StatusType.INFO
    ) -> None:
        """Display instruction message with appropriate styling.

        Args:
            message: The instruction message to display
            status_type: The type of status for styling (INFO, SUCCESS, WARNING, ERROR)
        """
        self.on_status(message, status_type)


async def login_command(server_url: str, skip_settings_sync: bool = False) -> bool:
    """Execute the login command.

    Args:
        server_url: OpenHands server URL to authenticate with
        skip_settings_sync: If True, skip syncing settings after login

    Returns:
        True if login was successful, False otherwise
    """
    console_print(
        f"[{OPENHANDS_THEME.accent}]Logging in to OpenHands Cloud..."
        f"[/{OPENHANDS_THEME.accent}]"
    )

    callback = ConsoleLoginCallback()
    return await run_login_flow(
        server_url=server_url,
        callback=callback,
        skip_settings_sync=skip_settings_sync,
        open_browser=True,
    )


def run_login_command(server_url: str) -> bool:
    """Run the login command synchronously.

    Args:
        server_url: OpenHands server URL to authenticate with

    Returns:
        True if login was successful, False otherwise
    """
    try:
        return asyncio.run(login_command(server_url))
    except KeyboardInterrupt:
        console_print(
            f"\n[{OPENHANDS_THEME.warning}]Login cancelled by "
            f"user.[/{OPENHANDS_THEME.warning}]"
        )
        return False
