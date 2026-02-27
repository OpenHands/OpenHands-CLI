"""Cloud login screen for OpenHands CLI.

This screen handles the OAuth device flow login within the TUI,
displaying status messages and the verification URL to the user.
"""

import logging
from collections.abc import Callable
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, LoadingIndicator, Rule, Static
from textual.worker import Worker, WorkerState

from openhands_cli.auth.login_service import run_login_flow


logger = logging.getLogger(__name__)


class TuiLoginCallback:
    """TUI-based implementation of LoginProgressCallback.

    Updates the CloudLoginScreen widgets with login progress.
    """

    def __init__(self, screen: "CloudLoginScreen"):
        """Initialize with reference to the screen.

        Args:
            screen: The CloudLoginScreen to update
        """
        self.screen = screen

    def on_status(self, message: str) -> None:
        """Update status in the TUI."""
        self.screen._update_status(message)

    def on_verification_url(self, url: str, user_code: str) -> None:
        """Show verification URL in the TUI."""
        self.screen._show_verification_url(url, user_code)

    def on_instructions(self, message: str) -> None:
        """Update instructions in the TUI."""
        self.screen._update_instructions(message)

    def on_browser_opened(self, success: bool) -> None:
        """Handle browser open result - status already updated by on_status."""
        pass  # Status message is handled by on_status callback

    def on_already_logged_in(self) -> None:
        """Handle already logged in state."""
        pass  # Status message is handled by on_status callback

    def on_token_expired(self) -> None:
        """Handle token expired state."""
        pass  # Status message is handled by on_status callback

    def on_login_success(self) -> None:
        """Handle login success."""
        pass  # Status message is handled by on_status callback

    def on_settings_synced(self, success: bool, error: str | None = None) -> None:
        """Handle settings sync result."""
        pass  # Instructions message is handled by on_instructions callback

    def on_error(self, error: str) -> None:
        """Handle error."""
        pass  # Status message is handled by on_status callback


class CloudLoginScreen(ModalScreen[bool]):
    """Screen for handling cloud login via OAuth device flow.

    Shows the login status and verification URL to the user.

    Attributes:
        auto_start_login: If True (default), automatically start the login
            flow when the screen is mounted. Set to False in subclasses
            for testing purposes.
    """

    BINDINGS: ClassVar = [
        ("escape", "cancel", "Cancel"),
    ]

    auto_start_login: ClassVar[bool] = True

    DEFAULT_CSS = """
    CloudLoginScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.8);
    }

    #cloud_login_container {
        padding: 2 4;
        width: 80;
        height: auto;
        min-width: 60;
        border: dashed $primary 80%;
        background: $surface 90%;
    }

    #login_title {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        text-style: bold;
        color: $primary;
        padding: 1 0;
    }

    #title_rule {
        margin: 0 0 1 0;
        color: $primary 50%;
    }

    #login_content {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 2;
    }

    #login_spinner {
        width: 100%;
        height: 3;
        content-align: center middle;
    }

    #login_spinner.hidden {
        display: none;
    }

    #login_status {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        color: $foreground;
        margin: 1 0;
    }

    #login_url {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        color: $primary;
        margin: 1 0;
        padding: 1 2;
        background: $surface;
        border: solid $primary 50%;
    }

    #login_url.hidden {
        display: none;
    }

    #login_instructions {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        color: $foreground 80%;
        margin: 1 0;
    }

    #login_instructions.hidden {
        display: none;
    }

    #login_actions {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 2;
        margin-top: 1;
    }

    #cancel_button {
        width: 40%;
        height: 3;
    }
    """

    def __init__(
        self,
        on_login_success: Callable[[], None] | None = None,
        on_login_cancelled: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the cloud login screen.

        Args:
            on_login_success: Callback when login succeeds
            on_login_cancelled: Callback when login is cancelled
        """
        super().__init__(**kwargs)
        self.on_login_success = on_login_success
        self.on_login_cancelled = on_login_cancelled
        self._login_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        with Container(id="cloud_login_container"):
            yield Label("Sign in with OpenHands Cloud", id="login_title")
            yield Rule(id="title_rule")

            with Vertical(id="login_content"):
                yield LoadingIndicator(id="login_spinner")
                yield Static("Initializing login...", id="login_status")
                yield Static("", id="login_url", classes="hidden")
                yield Static("", id="login_instructions", classes="hidden")

            with Vertical(id="login_actions"):
                yield Button(
                    "Cancel",
                    variant="default",
                    id="cancel_button",
                )

    def on_mount(self) -> None:
        """Start the login process when the screen is mounted."""
        if self.auto_start_login:
            self._start_login()

    def _start_login(self) -> None:
        """Start the cloud login worker."""
        self._login_worker = self.run_worker(
            self._run_cloud_login(),
            name="cloud_login",
            exclusive=True,
        )

    async def _run_cloud_login(self) -> bool:
        """Run the cloud login flow asynchronously.

        Returns:
            True if login was successful, False otherwise
        """
        callback = TuiLoginCallback(self)
        return await run_login_flow(
            callback=callback,
            skip_settings_sync=False,
            open_browser=True,
        )

    def _update_status(self, message: str) -> None:
        """Update the status message in the UI."""
        status = self.query_one("#login_status", Static)
        status.update(message)

    def _show_verification_url(self, url: str, user_code: str) -> None:
        """Show the verification URL to the user."""
        url_widget = self.query_one("#login_url", Static)
        url_widget.update(f"[bold]{url}[/bold]")
        url_widget.remove_class("hidden")

        instructions = self.query_one("#login_instructions", Static)
        instructions.update(f"Your code: [bold]{user_code}[/bold]")
        instructions.remove_class("hidden")

        # Hide spinner once we have URL
        spinner = self.query_one("#login_spinner", LoadingIndicator)
        spinner.add_class("hidden")

    def _update_instructions(self, message: str) -> None:
        """Update the instructions message."""
        instructions = self.query_one("#login_instructions", Static)
        instructions.update(message)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.worker.name != "cloud_login":
            return

        if event.state == WorkerState.SUCCESS:
            success = event.worker.result
            # Store callbacks before dismissing
            on_success = self.on_login_success if success else None
            on_cancelled = self.on_login_cancelled if not success else None

            # Dismiss the screen first
            if self.is_mounted:
                self.dismiss(success)

            # Then call the appropriate callback
            if on_success:
                try:
                    on_success()
                except Exception as e:
                    logger.error(f"Error in success callback: {e}", exc_info=True)
            elif on_cancelled:
                try:
                    on_cancelled()
                except Exception as e:
                    logger.error(f"Error in cancelled callback: {e}", exc_info=True)

        elif event.state == WorkerState.ERROR:
            self._update_status(f"Error: {event.worker.error}")
            self._update_instructions("Please try again or cancel.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel_button":
            self._cancel_login()

    def action_cancel(self) -> None:
        """Handle escape key to cancel login."""
        self._cancel_login()

    def _cancel_login(self) -> None:
        """Cancel the login process."""
        if self._login_worker and self._login_worker.is_running:
            self._login_worker.cancel()

        # Store callback before dismissing
        on_cancelled = self.on_login_cancelled

        if self.is_mounted:
            self.dismiss(False)

        if on_cancelled:
            try:
                on_cancelled()
            except Exception as e:
                logger.error(f"Error in cancel callback: {e}", exc_info=True)
