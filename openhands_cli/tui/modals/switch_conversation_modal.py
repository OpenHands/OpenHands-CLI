"""Switch conversation confirmation overlay for OpenHands CLI."""

from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Container, Grid
from textual.widgets import Button, Label


class SwitchConversationOverlay(Container):
    """Overlay widget with a dialog to confirm switching conversations.

    This is intentionally a widget (not a ModalScreen) so the underlying screen
    keeps rendering while the agent is running.
    """

    DEFAULT_CSS = """
    SwitchConversationOverlay {
        layer: overlay;
        width: 100%;
        height: 100%;
        align: center middle;
        background: rgba(0, 0, 0, 0.8);
    }

    SwitchConversationOverlay > #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto auto;
        padding: 1 2;
        width: 60;
        height: auto;
        min-width: 40;
        border: $primary 80%;
        background: $surface 90%;
        margin: 1 1;
    }

    SwitchConversationOverlay > #dialog > #question {
        column-span: 2;
        height: auto;
        width: 1fr;
        content-align: center middle;
        padding: 2 0;
    }

    SwitchConversationOverlay Button {
        width: 100%;
        height: 3;
        margin: 0 1;
    }

    SwitchConversationOverlay > #dialog > #yes {
        content-align: center middle;
    }

    SwitchConversationOverlay > #dialog > #no {
        content-align: center middle;
    }
    """

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
        if event.button.id == "yes":
            self.remove()
            self._on_confirmed()
            return
        if self._on_cancelled is not None:
            self.remove()
            self._on_cancelled()
        else:
            self.remove()
