"""User input widgets for the OpenHands CLI."""

from openhands_cli.refactor.widgets.user_input.expandable_text_area import (
    AutoGrowTextArea,
)
from openhands_cli.refactor.widgets.user_input.input_field import InputField
from openhands_cli.refactor.widgets.user_input.models import (
    CompletionItem,
    CompletionType,
)
from openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete import (
    TextAreaAutoComplete,
    detect_completion_type,
)


__all__ = [
    "AutoGrowTextArea",
    "CompletionItem",
    "CompletionType",
    "InputField",
    "TextAreaAutoComplete",
    "detect_completion_type",
]
