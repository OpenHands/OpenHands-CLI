from __future__ import annotations

import uuid
from dataclasses import dataclass

from textual.message import Message

from openhands.sdk.event import ActionEvent
from openhands_cli.user_actions.types import UserConfirmation


@dataclass
class ConversationCreated(Message):
    """Sent when a new conversation is created."""

    conversation_id: uuid.UUID


@dataclass
class ConversationSwitched(Message):
    """Sent when the app successfully switches to a different conversation."""

    conversation_id: uuid.UUID


@dataclass
class ConversationTitleUpdated(Message):
    """Sent when a conversation's title (first message) is determined."""

    conversation_id: uuid.UUID
    title: str


@dataclass
class SwitchConversationRequest(Message):
    """Sent by UI components to request a conversation switch."""

    conversation_id: str


@dataclass
class RevertSelectionRequest(Message):
    """Sent to request the history panel to revert highlight to current conversation."""

    pass


@dataclass
class ConfirmationNeeded(Message):
    """Posted when agent needs user confirmation for pending actions.

    The worker exits after posting this message (non-blocking).
    UI shows confirmation panel and waits for user input.
    """

    pending_actions: list[ActionEvent]


@dataclass
class ConfirmationProvided(Message):
    """Posted when user provides confirmation decision.

    UI posts this after user selects an option from the confirmation panel.
    A new worker is started to resume the conversation with the decision.
    """

    decision: UserConfirmation
