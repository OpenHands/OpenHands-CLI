"""Messages for conversation-related UI events.

Note: Most conversation state changes are now handled via StateManager's
reactive properties, which UI components watch directly. Only messages
that represent user intent/requests (not state) remain here.

See StateManager for conversation state (conversation_id, conversation_title,
is_switching, etc.) that UI components can watch via self.watch().
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.message import Message


@dataclass
class SwitchConversationRequest(Message):
    """Sent by UI components (like HistorySidePanel) to request a conversation switch.

    This represents user intent, not state change. The app handles this by
    calling ConversationManager.switch_to(), which updates StateManager.
    """

    conversation_id: str
