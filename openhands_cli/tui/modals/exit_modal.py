"""Exit confirmation modal for OpenHands CLI."""

from collections.abc import Callable
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label


class ExitConfirmationModal(ModalScreen):
    """Screen with a dialog to confirm exit."""

    CSS_PATH = "exit_modal.tcss"
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "exit_immediately", "Exit"),
    ]

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
        self.on_exit_cancelled = on_exit_cancelled

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Terminate session?", id="question"),
            Button("Yes, proceed", variant="error", id="yes"),
            Button("No, dismiss", variant="primary", id="no"),
            id="dialog",
        )
        yield Footer()

    def action_cancel(self) -> None:
        """Cancel exit and close modal."""
        self.dismiss()
        if self.on_exit_cancelled:
            try:
                self.on_exit_cancelled()
            except Exception as e:
                self.notify(f"Error during exit cancellation: {e}", severity="error")

    def action_exit_immediately(self) -> None:
        """Exit immediately without confirmation."""
        self.dismiss()
        try:
            self.on_exit_confirmed()
        except Exception:
            pass  # Ignore errors during forced exit

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
        if event.button.id == "yes":
            try:
                self.on_exit_confirmed()
            except Exception as e:
                self.notify(f"Error during exit confirmation: {e}", severity="error")

        elif self.on_exit_cancelled:
            try:
                self.on_exit_cancelled()
            except Exception as e:
                self.notify(f"Error during exit cancellation: {e}", severity="error")
