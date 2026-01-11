"""Autocomplete coordination logic extracted from InputField."""

from textual.widgets import TextArea

from openhands_cli.tui.widgets.user_input.models import (
    CompletionItem,
    CompletionType,
)
from openhands_cli.tui.widgets.user_input.text_area_with_autocomplete import (
    TextAreaAutoComplete,
)


class AutocompleteCoordinator:
    """Coordinates autocomplete behavior for a TextArea widget.

    This class encapsulates all autocomplete-related logic:
    - Updating candidates based on text changes
    - Handling keyboard navigation
    - Applying selected completions
    """

    def __init__(self, text_area: TextArea, autocomplete: TextAreaAutoComplete) -> None:
        self.text_area = text_area
        self.autocomplete = autocomplete

    def update_on_text_change(self) -> None:
        """Update autocomplete candidates when text changes."""
        self.autocomplete.update_candidates(self.text_area.text)

    def handle_key(self, key: str) -> bool:
        """Handle keyboard navigation for autocomplete.

        Returns True if the key was consumed by autocomplete.
        """
        return self.autocomplete.process_key(key)

    def handle_enter(self) -> bool:
        """Handle Enter key when autocomplete is visible.

        Returns True if autocomplete consumed the enter (completion selected).
        """
        if self.autocomplete.is_visible:
            return self.autocomplete.process_key("enter")
        return False

    def hide(self) -> None:
        """Hide the autocomplete dropdown."""
        self.autocomplete.hide_dropdown()

    @property
    def is_visible(self) -> bool:
        """Check if autocomplete dropdown is visible."""
        return self.autocomplete.is_visible

    def apply_completion(self, item: CompletionItem) -> None:
        """Apply the selected completion to the text area."""
        current_text = self.text_area.text
        completion_value = item.completion_value

        if item.completion_type == CompletionType.COMMAND:
            self.text_area.text = completion_value + " "
        elif item.completion_type == CompletionType.FILE:
            at_index = current_text.rfind("@")
            prefix = current_text[:at_index] if at_index >= 0 else ""
            self.text_area.text = prefix + completion_value + " "

        # Move cursor to end
        self.text_area.move_cursor((0, len(self.text_area.text)))
