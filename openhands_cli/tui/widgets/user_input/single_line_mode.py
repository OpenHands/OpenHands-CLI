"""Single-line input mode with autocomplete support."""

from textual.widget import Widget
from tui.widgets.user_input.single_line_input import (
    SingleLineInputWithWraping,
)

from openhands_cli.tui.widgets.user_input.autocomplete_coordinator import (
    AutocompleteCoordinator,
)
from openhands_cli.tui.widgets.user_input.input_mode import InputMode
from openhands_cli.tui.widgets.user_input.text_area_with_autocomplete import (
    TextAreaAutoComplete,
)


class SingleLineMode(InputMode):
    """Single-line input mode with auto-growing height and autocomplete.

    Features:
    - Uses SingleLineInputWithWraping with soft wrapping
    - Auto-grows height as text wraps (up to max-height)
    - Enter to submit, Shift+Enter/Ctrl+J for newline
    - Full autocomplete support for commands and file paths
    """

    def __init__(
        self,
        text_area: SingleLineInputWithWraping,
        autocomplete: TextAreaAutoComplete,
    ) -> None:
        self._text_area = text_area
        self._autocomplete = autocomplete
        self._coordinator = AutocompleteCoordinator(text_area, autocomplete)

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
        self._text_area.clear()

    def move_cursor_to_end(self) -> None:
        self._text_area.move_cursor(self._text_area.document.end)

    def show(self) -> None:
        self._text_area.display = True

    def hide(self) -> None:
        self._text_area.display = False

    def get_autocomplete_coordinator(self) -> AutocompleteCoordinator:
        return self._coordinator

    def on_deactivate(self) -> None:
        """Hide autocomplete when deactivating this mode."""
        self._coordinator.hide()
        super().on_deactivate()

    def handle_text_changed(self) -> None:
        """Update autocomplete when text changes."""
        self._coordinator.update_on_text_change()

    def handle_key(self, key: str) -> bool:
        """Handle key events for autocomplete navigation.

        Returns True if the key was consumed.
        """
        return self._coordinator.handle_key(key)

    def handle_enter_for_autocomplete(self) -> bool:
        """Handle Enter key when autocomplete might be visible.

        Returns True if autocomplete consumed the enter.
        """
        return self._coordinator.handle_enter()
