"""Exit confirmation modal for OpenHands CLI."""

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ExitConfirmationModal(ModalScreen):
    """Screen with a dialog to confirm exit."""

    CSS_PATH = "exit_modal.tcss"

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Terminate session?", id="question"),
            Button("Yes, proceed", variant="error", id="yes"),
            Button("No, dismiss", variant="primary", id="no"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes":
            self.app.exit()
        else:
            self.app.pop_screen()
