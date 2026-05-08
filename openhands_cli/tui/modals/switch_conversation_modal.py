"""Switch conversation confirmation modal for OpenHands CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


class SwitchConversationModal(ModalScreen[bool]):
    """Screen with a dialog to confirm switching conversations."""

    # Use the same look-and-feel as ExitConfirmationModal (semi-transparent dim).
    CSS_PATH = "exit_modal.tcss"
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "request_quit", "Exit"),
    ]

    def __init__(
        self,
        *,
        prompt: str,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(self._prompt, id="question"),
            Button("Yes, switch", variant="error", id="yes"),
            Button("No, stay", variant="primary", id="no"),
            id="dialog",
        )
        yield Footer()

    def action_cancel(self) -> None:
        """Cancel switch and close modal."""
        self.dismiss(False)

    def action_request_quit(self) -> None:
        """Handle ctrl+c - delegate to app's request_quit."""
        app = cast("OpenHandsApp", self.app)
        app.action_request_quit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")
