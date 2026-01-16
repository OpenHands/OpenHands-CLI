"""Cloud link modal for OpenHands CLI."""

from __future__ import annotations

import asyncio
import webbrowser
from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Grid, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, Static

from openhands_cli.auth.api_client import ApiClientError, OpenHandsApiClient
from openhands_cli.auth.device_flow import DeviceFlowClient, DeviceFlowError
from openhands_cli.auth.token_storage import TokenStorage


class CloudLinkModal(ModalScreen):
    """Modal for linking to OpenHands Cloud."""

    CSS_PATH = "cloud_link_modal.tcss"

    def __init__(
        self,
        is_connected: bool = False,
        on_link_complete: Callable[[bool], None] | None = None,
        cloud_url: str | None = None,
        **kwargs,
    ):
        """Initialize the cloud link modal.

        Args:
            is_connected: Whether currently connected to cloud
            on_link_complete: Callback when linking completes (success: bool)
            cloud_url: OpenHands Cloud URL for authentication
        """
        super().__init__(**kwargs)
        self.is_connected = is_connected
        self.on_link_complete = on_link_complete
        self._linking_in_progress = False

        # Import default here to avoid circular imports
        from openhands_cli.argparsers.main_parser import DEFAULT_CLOUD_URL

        self.cloud_url = cloud_url or DEFAULT_CLOUD_URL

    def compose(self) -> ComposeResult:
        with Grid(id="cloud_dialog"):
            if self.is_connected:
                yield Label(
                    "✓ Connected to OpenHands Cloud",
                    id="status_label",
                    classes="connected",
                )
                yield Static(
                    "Your CLI is linked to OpenHands Cloud.",
                    id="description",
                )
            else:
                yield Label(
                    "✗ Not connected to OpenHands Cloud",
                    id="status_label",
                    classes="disconnected",
                )
                yield Static(
                    "Link your CLI to OpenHands Cloud to sync settings and use cloud features.",
                    id="description",
                )

            # Only show override checkbox when not connected
            if not self.is_connected:
                with Vertical(id="options_container"):
                    yield Checkbox(
                        "Override local settings with cloud settings",
                        id="override_settings",
                        value=False,
                    )

            with Vertical(id="button_container"):
                if self.is_connected:
                    # Connected: show re-sync and close buttons
                    yield Button(
                        "Re-sync Cloud Settings",
                        variant="primary",
                        id="resync_button",
                    )
                    yield Button(
                        "Close",
                        variant="default",
                        id="cancel_button",
                    )
                else:
                    # Not connected: show link and cancel buttons
                    yield Button(
                        "Link to Cloud",
                        variant="primary",
                        id="link_button",
                    )
                    yield Button(
                        "Cancel",
                        variant="default",
                        id="cancel_button",
                    )

            yield Static("", id="status_message")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel_button":
            self.dismiss()
            return

        if event.button.id == "link_button" and not self._linking_in_progress:
            self._start_linking()

        if event.button.id == "resync_button" and not self._linking_in_progress:
            self._start_resync()

    def _start_linking(self) -> None:
        """Start the cloud linking process."""
        self._linking_in_progress = True

        # Update UI to show linking in progress
        link_button = self.query_one("#link_button", Button)
        link_button.disabled = True
        link_button.label = "Linking..."

        status_message = self.query_one("#status_message", Static)
        status_message.update("Opening browser for authentication...")

        # Start async linking
        asyncio.create_task(self._perform_linking())

    def _start_resync(self) -> None:
        """Start the cloud settings re-sync process."""
        self._linking_in_progress = True

        # Update UI to show resync in progress
        resync_button = self.query_one("#resync_button", Button)
        resync_button.disabled = True
        resync_button.label = "Syncing..."

        status_message = self.query_one("#status_message", Static)
        status_message.update("Syncing settings from cloud...")

        # Start async resync
        asyncio.create_task(self._perform_resync())

    async def _perform_resync(self) -> None:
        """Perform the cloud settings re-sync."""
        status_message = self.query_one("#status_message", Static)

        try:
            token_storage = TokenStorage()
            api_key = token_storage.get_api_key()

            if not api_key:
                status_message.update("Error: No API key found. Please re-link.")
                self._on_resync_failure()
                return

            await self._sync_settings(api_key)
            status_message.update("Settings synced successfully!")
            self._on_resync_success()

        except Exception as e:
            status_message.update(f"Error syncing settings: {e}")
            self._on_resync_failure()

    def _on_resync_success(self) -> None:
        """Handle successful resync."""
        resync_button = self.query_one("#resync_button", Button)
        resync_button.label = "Re-sync Cloud Settings"
        resync_button.disabled = False
        self._linking_in_progress = False

        if self.on_link_complete:
            self.on_link_complete(True)

    def _on_resync_failure(self) -> None:
        """Handle failed resync."""
        resync_button = self.query_one("#resync_button", Button)
        resync_button.label = "Re-sync Cloud Settings"
        resync_button.disabled = False
        self._linking_in_progress = False

    async def _perform_linking(self) -> None:
        """Perform the actual cloud linking."""
        status_message = self.query_one("#status_message", Static)
        override_checkbox = self.query_one("#override_settings", Checkbox)
        override_settings = override_checkbox.value

        try:
            # Check if already have a token
            token_storage = TokenStorage()
            existing_api_key = token_storage.get_api_key()

            if existing_api_key:
                # Already have a token, just sync settings if requested
                status_message.update("Already authenticated. Syncing settings...")
                if override_settings:
                    await self._sync_settings(existing_api_key)
                self._on_success()
                return

            # Start device flow authentication
            client = DeviceFlowClient(self.cloud_url)

            status_message.update("Starting authentication...")
            device_code, user_code, verification_uri, interval = (
                await client.start_device_flow()
            )

            # Build verification URL
            if "user_code=" in verification_uri:
                verification_url = verification_uri
            else:
                verification_url = f"{verification_uri}?user_code={user_code}"

            # Open browser
            status_message.update(
                f"Opening browser...\nIf browser doesn't open, visit:\n{verification_url}"
            )

            try:
                webbrowser.open(verification_url)
            except Exception:
                pass  # Browser opening is best-effort

            status_message.update("Waiting for authentication in browser...")

            # Poll for token
            tokens = await client.poll_for_token(device_code, interval)
            api_key = tokens.get("access_token")

            if not api_key:
                status_message.update("Authentication failed: No access token received")
                self._on_failure()
                return

            # Store the API key
            token_storage.store_api_key(api_key)

            status_message.update("Authentication successful!")

            # Sync settings if requested
            if override_settings:
                status_message.update("Syncing settings from cloud...")
                await self._sync_settings(api_key)

            self._on_success()

        except DeviceFlowError as e:
            status_message.update(f"Authentication failed: {e}")
            self._on_failure()
        except Exception as e:
            status_message.update(f"Error: {e}")
            self._on_failure()

    async def _sync_settings(self, api_key: str) -> None:
        """Sync settings from cloud."""
        client = OpenHandsApiClient(self.cloud_url, api_key)

        try:
            # Get LLM API key
            llm_api_key = await client.get_llm_api_key()

            # Get user settings
            settings = await client.get_user_settings()

            if llm_api_key and settings:
                # Create and save agent configuration
                # Note: This will overwrite existing settings without asking
                # since user explicitly checked the override checkbox
                from openhands_cli.stores import AgentStore
                from openhands_cli.stores.agent_store import resolve_llm_base_url

                store = AgentStore()
                base_url = resolve_llm_base_url(settings)
                store.create_and_save_from_settings(
                    llm_api_key=llm_api_key,
                    settings=settings,
                    base_url=base_url,
                )
        except ApiClientError:
            # Settings sync failed, but authentication succeeded
            pass

    def _on_success(self) -> None:
        """Handle successful linking."""
        self._linking_in_progress = False

        # Update status label
        status_label = self.query_one("#status_label", Label)
        status_label.update("✓ Connected to OpenHands Cloud")
        status_label.remove_class("disconnected")
        status_label.add_class("connected")

        # Update description
        description = self.query_one("#description", Static)
        description.update("Your CLI is now linked to OpenHands Cloud.")

        # Hide link button, show only cancel (now as "Close")
        try:
            link_button = self.query_one("#link_button", Button)
            link_button.display = False
        except Exception:
            pass

        cancel_button = self.query_one("#cancel_button", Button)
        cancel_button.label = "Close"

        # Update status message
        status_message = self.query_one("#status_message", Static)
        status_message.update("✓ Successfully linked to OpenHands Cloud!")

        # Call callback
        if self.on_link_complete:
            self.on_link_complete(True)

    def _on_failure(self) -> None:
        """Handle failed linking."""
        self._linking_in_progress = False

        # Re-enable link button
        try:
            link_button = self.query_one("#link_button", Button)
            link_button.disabled = False
            link_button.label = "Link to Cloud"
        except Exception:
            pass
