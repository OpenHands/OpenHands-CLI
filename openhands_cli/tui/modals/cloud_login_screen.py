"""Cloud login screen for OpenHands CLI.

This screen handles the OAuth device flow login within the TUI,
displaying status messages and the verification URL to the user.
"""

import os
import webbrowser
from collections.abc import Callable
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, LoadingIndicator, Rule, Static
from textual.worker import Worker, WorkerState


class CloudLoginScreen(ModalScreen[bool]):
    """Screen for handling cloud login via OAuth device flow.

    Shows the login status and verification URL to the user.
    """

    BINDINGS: ClassVar = [
        ("escape", "cancel", "Cancel"),
    ]

    CSS_PATH = "cloud_login_screen.tcss"

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
        from openhands_cli.auth.api_client import (
            ApiClientError,
            fetch_user_data_after_oauth,
        )
        from openhands_cli.auth.device_flow import (
            DeviceFlowClient,
            DeviceFlowError,
        )
        from openhands_cli.auth.token_storage import TokenStorage
        from openhands_cli.auth.utils import is_token_valid

        server_url = os.getenv("OPENHANDS_CLOUD_URL", "https://app.all-hands.dev")
        token_storage = TokenStorage()

        # Check for existing valid token
        existing_api_key = token_storage.get_api_key()
        if existing_api_key and await is_token_valid(server_url, existing_api_key):
            self._update_status("Already logged in. Syncing settings...")
            try:
                await fetch_user_data_after_oauth(server_url, existing_api_key)
                self._update_status("✓ Settings synchronized!")
                return True
            except ApiClientError as e:
                self._update_status(f"Warning: Could not sync settings: {e}")
                return True

        # Start device flow
        self._update_status("Connecting to OpenHands Cloud...")
        client = DeviceFlowClient(server_url)

        try:
            # Step 1: Get device authorization
            auth_response = await client.start_device_flow()

            # Step 2: Show URL and instructions to user
            verification_url = auth_response.verification_uri_complete
            user_code = auth_response.user_code

            self._show_verification_url(verification_url, user_code)

            # Try to open browser
            try:
                webbrowser.open(verification_url)
                self._update_status("Browser opened. Complete login in your browser.")
            except Exception:
                self._update_status("Please open the URL above in your browser.")

            # Step 3: Poll for token
            self._update_instructions("Waiting for authentication to complete...")
            token_response = await client.poll_for_token(
                auth_response.device_code, auth_response.interval
            )

            # Step 4: Store the token
            token_storage.store_api_key(token_response.access_token)
            self._update_status("✓ Logged into OpenHands Cloud!")

            # Step 5: Fetch user data
            self._update_instructions("Syncing settings...")
            try:
                await fetch_user_data_after_oauth(
                    server_url, token_response.access_token
                )
                self._update_instructions("✓ Settings synchronized!")
            except ApiClientError as e:
                self._update_instructions(f"Warning: Could not sync settings: {e}")

            return True

        except DeviceFlowError as e:
            self._update_status(f"Authentication failed: {e}")
            self._update_instructions("Please try again.")
            return False

    def _update_status(self, message: str) -> None:
        """Update the status message in the UI."""
        self.call_from_thread(self._set_status, message)

    def _set_status(self, message: str) -> None:
        """Set the status message (must be called from main thread)."""
        status = self.query_one("#login_status", Static)
        status.update(message)

    def _show_verification_url(self, url: str, user_code: str) -> None:
        """Show the verification URL to the user."""
        self.call_from_thread(self._set_verification_url, url, user_code)

    def _set_verification_url(self, url: str, user_code: str) -> None:
        """Set the verification URL (must be called from main thread)."""
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
        self.call_from_thread(self._set_instructions, message)

    def _set_instructions(self, message: str) -> None:
        """Set the instructions (must be called from main thread)."""
        instructions = self.query_one("#login_instructions", Static)
        instructions.update(message)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.worker.name != "cloud_login":
            return

        if event.state == WorkerState.SUCCESS:
            success = event.worker.result
            self.dismiss(success)
            if success and self.on_login_success:
                try:
                    self.on_login_success()
                except Exception as e:
                    self.notify(f"Error after login: {e}", severity="error")
            elif not success and self.on_login_cancelled:
                try:
                    self.on_login_cancelled()
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")

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

        self.dismiss(False)
        if self.on_login_cancelled:
            try:
                self.on_login_cancelled()
            except Exception as e:
                self.notify(f"Error during cancel: {e}", severity="error")
