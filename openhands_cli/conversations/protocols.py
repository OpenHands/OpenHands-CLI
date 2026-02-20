from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from openhands.sdk import Event
from openhands_cli.conversations.models import ConversationMetadata


class ConversationStore(Protocol):
    """Protocol for conversation storage access."""

    def list_conversations(self, limit: int = 100) -> list[ConversationMetadata]:
        """List recent conversations.

        Args:
            limit: Maximum number of conversations to return.

        Returns:
            List of conversation metadata sorted by creation date (newest first).
        """
        ...

    def get_metadata(self, conversation_id: str) -> ConversationMetadata | None:
        """Get metadata for a specific conversation.

        Args:
            conversation_id: The conversation ID.

        Returns:
            Metadata if found, None otherwise.
        """
        ...

    def get_event_count(self, conversation_id: str) -> int:
        """Get the total number of events in a conversation.

        Args:
            conversation_id: The conversation ID.

        Returns:
            Total count of events.
        """
        ...

    def load_events(
        self,
        conversation_id: str,
        limit: int | None = None,
        start_from_newest: bool = False,
    ) -> Iterator[Event]:
        """Load events for a conversation.

        Args:
            conversation_id: The conversation ID.
            limit: Optional maximum number of events to load.
            start_from_newest: If True and limit is set, loads the *last* N events
                             (chronologically). If False, loads the *first* N events.

        Returns:
            Iterator of events.
        """
        ...

    def exists(self, conversation_id: str) -> bool:
        """Check if a conversation exists.

        Args:
            conversation_id: The conversation ID.

        Returns:
            True if exists, False otherwise.
        """
        ...

    def create(self, conversation_id: str | None = None) -> str:
        """Create a new conversation.

        Args:
            conversation_id: Optional ID for the new conversation.
                           If not provided, one will be generated.

        Returns:
            The conversation ID.
        """
        ...
