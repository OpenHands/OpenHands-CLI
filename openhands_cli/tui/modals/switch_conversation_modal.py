"""Switch conversation confirmation modal for OpenHands CLI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class SwitchConversationModal(ModalScreen[bool]):
    """Screen with a dialog to confirm switching conversations."""

    # Use the same look-and-feel as ExitConfirmationModal (semi-transparent dim).
    CSS_PATH = "exit_modal.tcss"

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")
