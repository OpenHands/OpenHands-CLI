"""Shared confirmation modal behavior for two-button dialogs."""

from __future__ import annotations

from typing import ClassVar, TypeVar

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label


DismissResult = TypeVar("DismissResult")


class BinaryConfirmationModal(ModalScreen[DismissResult]):
    """Base modal for binary confirmation prompts."""

    AUTO_FOCUS = "#no"
    CSS_PATH = "exit_modal.tcss"
    BINDINGS: ClassVar = [
        ("left", "focus_left_choice", "Focus left choice"),
        ("right", "focus_right_choice", "Focus right choice"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        *,
        prompt: str,
        confirm_label: str,
        cancel_label: str,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._prompt = prompt
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(self._prompt, id="question"),
            Button(self._confirm_label, variant="error", id="yes"),
            Button(self._cancel_label, variant="primary", id="no"),
            id="dialog",
        )

    def action_focus_left_choice(self) -> None:
        self.query_one("#yes", Button).focus()

    def action_focus_right_choice(self) -> None:
        self.query_one("#no", Button).focus()

    def action_cancel(self) -> None:
        self._handle_choice(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._handle_choice(event.button.id == "yes")

    def _handle_choice(self, confirmed: bool) -> None:
        dismiss_result = self.get_dismiss_result(confirmed)
        if dismiss_result is None:
            self.dismiss()
        else:
            self.dismiss(dismiss_result)
        self.handle_choice(confirmed)

    def get_dismiss_result(self, _confirmed: bool) -> DismissResult | None:
        return None

    def handle_choice(self, confirmed: bool) -> None:
        pass
