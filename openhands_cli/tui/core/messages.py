from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.message import Message


if TYPE_CHECKING:
    from openhands.sdk.event.base import Event
    from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


@dataclass
class ConversationCreated(Message):
    """Sent when a new conversation is created."""

    conversation_id: uuid.UUID


@dataclass
class RenderConversationHistory(Message):
    """Sent to request ConversationPane to render history events.

    The conversation_id allows routing to the correct pane in multi-chat mode.
    """

    conversation_id: uuid.UUID
    events: Sequence[Event]
    visualizer: ConversationVisualizer


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
