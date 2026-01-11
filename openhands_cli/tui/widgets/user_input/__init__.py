"""User input widgets for the OpenHands CLI."""

from openhands_cli.tui.widgets.user_input.autocomplete_coordinator import (
    AutocompleteCoordinator,
)
from openhands_cli.tui.widgets.user_input.expandable_text_area import (
    AutoGrowTextArea,
)
from openhands_cli.tui.widgets.user_input.input_field import InputField
from openhands_cli.tui.widgets.user_input.input_mode import InputMode
from openhands_cli.tui.widgets.user_input.models import (
    CompletionItem,
    CompletionType,
)
from openhands_cli.tui.widgets.user_input.multiline_mode import MultilineMode
from openhands_cli.tui.widgets.user_input.single_line_mode import SingleLineMode
from openhands_cli.tui.widgets.user_input.text_area_with_autocomplete import (
    TextAreaAutoComplete,
    detect_completion_type,
)


__all__ = [
    "AutocompleteCoordinator",
    "AutoGrowTextArea",
    "CompletionItem",
    "CompletionType",
    "InputField",
    "InputMode",
    "MultilineMode",
    "SingleLineMode",
    "TextAreaAutoComplete",
    "detect_completion_type",
]
