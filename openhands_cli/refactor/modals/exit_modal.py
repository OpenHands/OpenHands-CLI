"""Exit confirmation modal for OpenHands CLI."""

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ExitConfirmationModal(ModalScreen):
    """Screen with a dialog to confirm exit."""

    CSS_PATH = "exit_modal.tcss"

    def __init__(
        self,
        on_exit_confirmed: Callable[[], None] | None = None,
        on_exit_cancelled: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the exit confirmation modal.

        Args:
            on_exit_confirmed: Callback to invoke when exit is confirmed
            on_exit_cancelled: Callback to invoke when exit is cancelled
        """
        super().__init__(**kwargs)
        self.on_exit_confirmed = on_exit_confirmed or (lambda: self.app.exit())
        self.on_exit_cancelled = on_exit_cancelled or (lambda: self.app.pop_screen())

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Terminate session?", id="question"),
            Button("Yes, proceed", variant="error", id="yes"),
            Button("No, dismiss", variant="primary", id="no"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes":
            # Dismiss the modal first, then call the callback
            self.dismiss()
            self.on_exit_confirmed()
        else:
            # Dismiss the modal first, then call the callback
            self.dismiss()
            self.on_exit_cancelled()
