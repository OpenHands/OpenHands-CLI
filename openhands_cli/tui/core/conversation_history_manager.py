"""Manager for paginated conversation history.

This manager handles the pagination state for a single conversation's
event history. It wraps ConversationHistoryState and provides a clean
interface for:
- Resetting state when switching/resuming conversations
- Getting the initial page of recent events
- Loading more events on demand (pagination)

The actual rendering (widget creation, mounting) is done by ConversationPane,
keeping data management separate from UI concerns.

Note: This is about events within ONE conversation, not the list of all
conversations (which is handled by HistorySidePanel).
"""

from collections.abc import Sequence

from openhands.sdk.event.base import Event
from openhands_cli.tui.core.conversation_history import (
    DEFAULT_PAGE_SIZE,
    ConversationHistoryState,
    create_conversation_history_state,
)


class ConversationHistoryManager:
    """Manages pagination state for a single conversation's event history.

    Responsibilities:
    - Track which events have been rendered
    - Provide pages of events on demand
    - Reset state when switching conversations

    Used by ConversationPane for rendering history.
    """

    def __init__(self, page_size: int = DEFAULT_PAGE_SIZE) -> None:
        self._page_size = page_size
        self._state: ConversationHistoryState | None = None

    @property
    def has_more(self) -> bool:
        """Check if there are more events available to load."""
        return bool(self._state and self._state.has_more)

    def reset(self, events: Sequence[Event]) -> list[Event]:
        """Reset state with new events and return the initial page.

        Called when switching to or resuming a conversation.
        Returns the most recent events (up to page_size).
        """
        self._state = create_conversation_history_state(
            events, page_size=self._page_size
        )
        return self._state.get_initial_page()

    def next_page(self) -> list[Event]:
        """Get the next page of older events (for 'load more')."""
        if not self._state:
            return []
        return self._state.get_next_page()
