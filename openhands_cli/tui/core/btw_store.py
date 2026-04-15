"""BTW (By The Way) store for tracking side-channel questions.

This module provides a store for managing BTW entries - questions that users
ask via /btw command without disrupting the main task flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BtwStatus(Enum):
    """Status of a BTW entry."""
    PENDING = "pending"
    DONE = "done"
    ERROR = "error"


@dataclass
class BtwEntry:
    """A single BTW entry representing a side-channel question."""
    id: str
    question: str
    response: str | None = None
    status: BtwStatus = BtwStatus.PENDING


class BtwStore:
    """Store for BTW entries scoped to conversations.

    This is a simple in-memory store that tracks pending, resolved, and failed
    BTW entries per conversation.
    """

    def __init__(self) -> None:
        self._entries_by_conversation: dict[str, list[BtwEntry]] = {}

    def add_pending(self, conversation_id: str, question: str) -> str:
        """Add a pending BTW entry.

        Args:
            conversation_id: The conversation ID.
            question: The question to ask.

        Returns:
            The ID of the new entry.
        """
        import uuid

        entry_id = str(uuid.uuid4())
        entries = self._entries_by_conversation.setdefault(conversation_id, [])
        entries.append(BtwEntry(id=entry_id, question=question, status=BtwStatus.PENDING))
        return entry_id

    def resolve(self, conversation_id: str, entry_id: str, response: str) -> None:
        """Mark a BTW entry as resolved.

        Args:
            conversation_id: The conversation ID.
            entry_id: The entry ID.
            response: The agent's response.
        """
        entries = self._entries_by_conversation.get(conversation_id, [])
        for entry in entries:
            if entry.id == entry_id:
                entry.response = response
                entry.status = BtwStatus.DONE
                break

    def fail(self, conversation_id: str, entry_id: str, error: str) -> None:
        """Mark a BTW entry as failed.

        Args:
            conversation_id: The conversation ID.
            entry_id: The entry ID.
            error: The error message.
        """
        entries = self._entries_by_conversation.get(conversation_id, [])
        for entry in entries:
            if entry.id == entry_id:
                entry.response = error
                entry.status = BtwStatus.ERROR
                break

    def dismiss(self, conversation_id: str, entry_id: str) -> None:
        """Dismiss (remove) a BTW entry.

        Args:
            conversation_id: The conversation ID.
            entry_id: The entry ID to dismiss.
        """
        entries = self._entries_by_conversation.get(conversation_id, [])
        self._entries_by_conversation[conversation_id] = [
            e for e in entries if e.id != entry_id
        ]

    def get_entries(self, conversation_id: str) -> list[BtwEntry]:
        """Get all BTW entries for a conversation.

        Args:
            conversation_id: The conversation ID.

        Returns:
            List of BTW entries.
        """
        return list(self._entries_by_conversation.get(conversation_id, []))

    def clear(self, conversation_id: str | None = None) -> None:
        """Clear BTW entries.

        Args:
            conversation_id: If provided, clear only entries for this conversation.
                           If None, clear all entries.
        """
        if conversation_id is None:
            self._entries_by_conversation.clear()
        elif conversation_id in self._entries_by_conversation:
            del self._entries_by_conversation[conversation_id]


# Global singleton instance
_btw_store: BtwStore | None = None


def get_btw_store() -> BtwStore:
    """Get the global BTW store instance."""
    global _btw_store
    if _btw_store is None:
        _btw_store = BtwStore()
    return _btw_store