"""Multiline input mode for explicit multiline editing."""

from textual.widget import Widget
from textual.widgets import TextArea

from openhands_cli.tui.widgets.user_input.input_mode import InputMode


class MultilineMode(InputMode):
    """Multiline input mode for explicit multiline editing.

    Features:
    - Uses larger TextArea for multi-line content
    - Ctrl+J to submit
    - No autocomplete (simpler editing experience)
    """

    def __init__(self, text_area: TextArea) -> None:
        self._text_area = text_area

    @property
    def widget(self) -> Widget:
        return self._text_area

    @property
    def text(self) -> str:
        return self._text_area.text

    @text.setter
    def text(self, value: str) -> None:
        self._text_area.text = value

    def focus(self) -> None:
        self._text_area.focus()

    def clear(self) -> None:
        self._text_area.text = ""

    def move_cursor_to_end(self) -> None:
        self._text_area.move_cursor(self._text_area.document.end)

    def show(self) -> None:
        self._text_area.display = True

    def hide(self) -> None:
        self._text_area.display = False
