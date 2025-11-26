"""Exit confirmation modal for OpenHands CLI."""

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ExitConfirmationModal(ModalScreen):
    """Screen with a dialog to confirm exit."""

    DEFAULT_CSS = """
    ExitConfirmationModal {
        align: center middle;
    }

    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 0 1;
        width: 25vw;
        height: 5vw;
        border: $primary 80%;
        background: $surface;
        margin: 1 1;
    }

    #question {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }

    Button {
        width: 100%;
    }
    """

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
