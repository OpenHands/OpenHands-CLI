"""Pydantic models for user input components."""

from enum import StrEnum

from pydantic import BaseModel


class CompletionType(StrEnum):
    """Type of completion being performed."""

    COMMAND = "command"
    FILE = "file"
    NONE = "none"


class CompletionItem(BaseModel):
    """A completion item with display and insertion values.

    Attributes:
        display_text: The text shown in the dropdown (e.g., "📁 @src/")
        completion_value: The value to insert (e.g., "@src/")
        completion_type: The type of completion (command or file)
    """

    display_text: str
    completion_value: str
    completion_type: CompletionType

    model_config = {"frozen": True}
