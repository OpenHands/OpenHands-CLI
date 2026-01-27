"""Message definitions for TUI inter-widget communication.

This module defines the messages that flow between widgets following
Textual's message bubbling pattern. Messages bubble up the DOM tree
from child to parent, allowing ancestor widgets to handle them.

Message Flow:
    InputField
        ↓
    ConversationView(#input_area)
        ↓
    MainDisplay(#main_display)  ← Handles UserInputSubmitted (renders message)
        ↓
    OpenHandsApp                ← Handles SlashCommandSubmitted (executes command)
"""

from pydantic.dataclasses import dataclass
from textual.message import Message


@dataclass
class UserInputSubmitted(Message):
    """Message sent when user submits regular text input.

    This message is handled by MainDisplay to render the user message,
    then bubbles to App to send to the agent.
    """

    content: str


@dataclass
class SlashCommandSubmitted(Message):
    """Message sent when user submits a slash command.

    This message bubbles directly to App for command execution.
    MainDisplay ignores it (doesn't render commands as user messages).
    """

    command: str
    args: str = ""

    @property
    def full_command(self) -> str:
        """Return the full command string with leading slash."""
        return f"/{self.command}"
