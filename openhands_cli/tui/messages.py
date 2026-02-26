"""Message definitions for TUI inter-widget communication.

This module defines the messages that flow between widgets following
Textual's message bubbling pattern. Messages bubble up the DOM tree
from child to parent, allowing ancestor widgets to handle them.

Message Flow:
    InputField
        ↓
    InputAreaContainer ← Handles SlashCommandSubmitted (routes to ConversationManager)
        ↓
    ConversationManager ← Handles SendMessage (renders and processes)
        ↓
    OpenHandsApp       ← Handles app-level concerns (modals, notifications)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic.dataclasses import dataclass
from textual.message import Message


if TYPE_CHECKING:
    from openhands.sdk.critic.result import CriticResult


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


class SendMessage(Message):
    """Request to send a user message to the current conversation.

    This starts a new user turn and resets the refinement iteration counter.
    Use SendRefinementMessage for system-generated refinement messages.
    """

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content


class SendRefinementMessage(Message):
    """Request to send a refinement message to the current conversation.

    Unlike SendMessage, this preserves the refinement iteration counter,
    allowing the iterative refinement loop to track progress correctly.
    """

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content


class CriticResultReceived(Message):
    """Notification that a critic result was received.

    Posted by the visualizer when a critic result is received on an event.
    The RefinementController handles this to evaluate and trigger refinement.
    """

    def __init__(self, critic_result: CriticResult) -> None:
        super().__init__()
        self.critic_result = critic_result
