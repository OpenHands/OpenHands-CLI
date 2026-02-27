"""Welcome modal for first-time setup in OpenHands CLI.

This modal is shown to first-time users and offers two options:
1. Enter LLM settings manually
2. Sign in with OpenHands Cloud
"""

from collections.abc import Callable
from typing import ClassVar, Literal

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Rule


WelcomeChoice = Literal["llm_settings", "cloud_login"]


class WelcomeModal(ModalScreen[WelcomeChoice | None]):
    """Modal screen for first-time users to choose setup method.

    Presents two options:
    - Enter LLM settings (opens existing SettingsScreen)
    - Sign in with OpenHands Cloud (runs cloud login flow)
    """

    BINDINGS: ClassVar = [
        ("escape", "cancel", "Cancel"),
    ]

    CSS_PATH = "welcome_modal.tcss"

    def __init__(
        self,
        on_llm_settings: Callable[[], None] | None = None,
        on_cloud_login: Callable[[], None] | None = None,
        on_cancelled: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the welcome modal.

        Args:
            on_llm_settings: Callback when user chooses LLM settings option
            on_cloud_login: Callback when user chooses cloud login option
            on_cancelled: Callback when user cancels the modal
        """
        super().__init__(**kwargs)
        self.on_llm_settings = on_llm_settings
        self.on_cloud_login = on_cloud_login
        self.on_cancelled = on_cancelled

    def compose(self) -> ComposeResult:
        with Container(id="welcome_container"):
            yield Label("Welcome to OpenHands", id="welcome_title")
            yield Rule(id="title_rule")

            with Vertical(id="welcome_buttons"):
                yield Button(
                    "Enter your LLM settings",
                    variant="warning",
                    id="llm_settings_button",
                )

                yield Label("or", id="or_label")

                yield Button(
                    "Sign in with OpenHands Cloud",
                    variant="default",
                    id="cloud_login_button",
                    classes="cloud-button",
                )

            yield Label(
                "You can change this later in Settings",
                id="settings_hint",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "llm_settings_button":
            self.dismiss("llm_settings")
            if self.on_llm_settings:
                try:
                    self.on_llm_settings()
                except Exception as e:
                    self.notify(
                        f"Error opening LLM settings: {e}", severity="error"
                    )
        elif event.button.id == "cloud_login_button":
            self.dismiss("cloud_login")
            if self.on_cloud_login:
                try:
                    self.on_cloud_login()
                except Exception as e:
                    self.notify(
                        f"Error during cloud login: {e}", severity="error"
                    )

    def action_cancel(self) -> None:
        """Handle escape key to cancel the welcome modal."""
        self.dismiss(None)
        if self.on_cancelled:
            try:
                self.on_cancelled()
            except Exception as e:
                self.notify(f"Error during cancel: {e}", severity="error")
