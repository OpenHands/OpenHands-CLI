"""Switch conversation confirmation modal for OpenHands CLI."""

from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class SwitchConversationModal(ModalScreen):
    """Screen with a dialog to confirm switching conversations."""

    # Use the same look-and-feel as ExitConfirmationModal (semi-transparent dim).
    CSS_PATH = "exit_modal.tcss"

    def __init__(
        self,
        *,
        prompt: str,
        on_confirmed: Callable[[], None],
        on_cancelled: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._prompt = prompt
        self._on_confirmed = on_confirmed
        self._on_cancelled = on_cancelled

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(self._prompt, id="question"),
            Button("Yes, switch", variant="error", id="yes"),
            Button("No, stay", variant="primary", id="no"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
        if event.button.id == "yes":
            self._on_confirmed()
            return
        if self._on_cancelled is not None:
            self._on_cancelled()
