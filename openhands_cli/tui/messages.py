"""Message definitions for TUI inter-widget communication.

This module defines the messages that flow between widgets following
Textual's message bubbling pattern. Messages bubble up the DOM tree
from child to parent, allowing ancestor widgets to handle them.

Message Flow:
    InputField
        ↓
    MainDisplay(#main_display)  ← Handles UserInputSubmitted (renders message)
                                ← Handles SlashCommandSubmitted (posts domain messages)
        ↓
    ConversationView            ← Handles NewConversationRequested
        ↓
    OpenHandsApp                ← Handles app-level concerns (modals, notifications)
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


class NewConversationRequested(Message):
    """Message sent when user requests a new conversation (via /new command).

    This message is posted by MainDisplay and handled by ConversationView,
    which owns the conversation lifecycle and state.
    """

    pass


@dataclass
class ProcessUserInput(Message):
    """Message sent when user input needs to be processed by the agent.

    This message is posted by MainDisplay after rendering the user message,
    and handled by ConversationView which owns the ConversationRunner.

    Flow:
        UserInputSubmitted → MainDisplay (renders) → ProcessUserInput → ConversationView (processes)
    """

    content: str
