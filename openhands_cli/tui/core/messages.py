from __future__ import annotations

import uuid
from dataclasses import dataclass

from textual.message import Message


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
