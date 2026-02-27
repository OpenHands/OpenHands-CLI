"""Login command implementation for OpenHands CLI."""

import asyncio
import html

from openhands_cli.auth.login_service import run_login_flow
from openhands_cli.auth.utils import console_print
from openhands_cli.theme import OPENHANDS_THEME


class ConsoleLoginCallback:
    """Console-based implementation of LoginProgressCallback.

    Displays login progress using Rich console output.
    """

    def on_status(self, message: str) -> None:
        """Display status message."""
        # Check for specific message patterns to apply appropriate styling
        if message.startswith("✓"):
            console_print(f"[{OPENHANDS_THEME.success}]{message}[/{OPENHANDS_THEME.success}]")
        elif "failed" in message.lower() or "error" in message.lower():
            console_print(f"[{OPENHANDS_THEME.error}]{message}[/{OPENHANDS_THEME.error}]")
        elif "expired" in message.lower() or "logging out" in message.lower():
            console_print(f"[{OPENHANDS_THEME.warning}]{message}[/{OPENHANDS_THEME.warning}]")
        else:
            console_print(f"[{OPENHANDS_THEME.accent}]{message}[/{OPENHANDS_THEME.accent}]")

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

    def on_instructions(self, message: str) -> None:
        """Display instruction message."""
        if message.startswith("✓"):
            console_print(f"[{OPENHANDS_THEME.success}]{message}[/{OPENHANDS_THEME.success}]")
        elif "warning" in message.lower():
            console_print(f"[{OPENHANDS_THEME.warning}]{message}[/{OPENHANDS_THEME.warning}]")
        else:
            console_print(f"[{OPENHANDS_THEME.secondary}]{message}[/{OPENHANDS_THEME.secondary}]")

    def on_browser_opened(self, success: bool) -> None:
        """Handle browser open result."""
        if success:
            console_print(
                f"[{OPENHANDS_THEME.success}]✓ Browser "
                f"opened successfully[/{OPENHANDS_THEME.success}]"
            )
        else:
            console_print(
                f"[{OPENHANDS_THEME.warning}]Could not open browser automatically."
                f"[/{OPENHANDS_THEME.warning}]"
            )

    def on_already_logged_in(self) -> None:
        """Handle already logged in state."""
        console_print(
            f"[{OPENHANDS_THEME.warning}]You are already logged in to "
            f"OpenHands Cloud.[/{OPENHANDS_THEME.warning}]"
        )

    def on_token_expired(self) -> None:
        """Handle token expired state."""
        console_print(
            f"[{OPENHANDS_THEME.warning}]Token is invalid or expired."
            f"[/{OPENHANDS_THEME.warning}]"
        )

    def on_login_success(self) -> None:
        """Handle login success."""
        console_print(
            f"[{OPENHANDS_THEME.secondary}]Your authentication "
            f"tokens have been stored securely.[/{OPENHANDS_THEME.secondary}]"
        )

    def on_settings_synced(self, success: bool, error: str | None = None) -> None:
        """Handle settings sync result."""
        if success:
            console_print(
                f"\n[{OPENHANDS_THEME.success}]✓ Settings synchronized "
                f"successfully![/{OPENHANDS_THEME.success}]"
            )
        else:
            safe_error = html.escape(str(error)) if error else "Unknown error"
            console_print(
                f"\n[{OPENHANDS_THEME.warning}]Warning: "
                f"Could not fetch user data: {safe_error}[/{OPENHANDS_THEME.warning}]"
            )
            console_print(
                f"[{OPENHANDS_THEME.secondary}]Please try: [bold]"
                f"{html.escape('openhands logout && openhands login')}"
                f"[/bold][/{OPENHANDS_THEME.secondary}]"
            )

    def on_error(self, error: str) -> None:
        """Handle error."""
        console_print(
            f"[{OPENHANDS_THEME.error}]Authentication failed: "
            f"{error}[/{OPENHANDS_THEME.error}]"
        )


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
