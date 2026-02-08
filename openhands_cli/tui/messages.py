"""Message definitions for TUI inter-widget communication.

This module defines the messages that flow between widgets following
Textual's message bubbling pattern. Messages bubble up the DOM tree
from child to parent, allowing ancestor widgets to handle them.

Message Flow:
    InputField
        ↓
    InputAreaContainer ← Handles SlashCommandSubmitted (routes to ConversationManager)
        ↓
    ConversationManager ← Handles UserInputSubmitted (renders and processes)
        ↓
    OpenHandsApp       ← Handles app-level concerns (modals, notifications)
"""

from pydantic.dataclasses import dataclass
from textual.message import Message


@dataclass
class UserInputSubmitted(Message):
    """Message sent when user submits regular text input.

    This message bubbles up to ConversationContainer which renders the user message
    and processes it with the conversation runner.
    """

    content: str


@dataclass
class SlashCommandSubmitted(Message):
    """Message sent when user submits a slash command.

    This message is handled by InputAreaContainer for command execution.
    """

    command: str
    args: str = ""

    @property
    def full_command(self) -> str:
        """Return the full command string with leading slash."""
        return f"/{self.command}"


class NewConversationRequested(Message):
    """Message sent when user requests a new conversation (via /new command).

    This message is handled by ConversationContainer, which owns the conversation
    lifecycle and state.
    """

    pass
