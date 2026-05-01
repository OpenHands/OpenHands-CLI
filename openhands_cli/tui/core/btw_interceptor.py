"""BTW (By The Way) interceptor for handling side-channel questions.

This module provides a class that intercepts /btw commands and routes them
through the ask_agent side-channel without disrupting the main task flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from openhands_cli.tui.core.btw_store import BtwStore


if TYPE_CHECKING:
    from openhands_cli.tui.core.btw_store import BtwEntry


# The /btw command prefix
BTW_COMMAND = "/btw"
BTW_PREFIX = f"{BTW_COMMAND} "


@dataclass
class BtwResult:
    """Result of processing a message through the BTW interceptor."""

    is_btw: bool
    question: str | None = None
    entry_id: str | None = None


class BtwInterceptor:
    """Interceptor for /btw commands.

    Handles command parsing and store management for side-channel questions.
    The actual API call is the caller's responsibility.
    """

    def __init__(
        self,
        store: BtwStore,
        conversation_id: str | None = None,
    ) -> None:
        self._store = store
        self._conversation_id = conversation_id

    def set_conversation_id(self, conversation_id: str | None) -> None:
        """Update the conversation ID."""
        self._conversation_id = conversation_id

    def process(self, message: str) -> BtwResult:
        """Process a message to check if it's a BTW command.

        Returns:
            BtwResult indicating if it's a BTW command and details.
        """
        trimmed = message.strip()
        is_btw = trimmed == BTW_COMMAND or trimmed.startswith(BTW_PREFIX)

        if not self._conversation_id or not is_btw:
            return BtwResult(is_btw=False)

        question = trimmed[len(BTW_COMMAND) :].strip()
        if not question:
            return BtwResult(is_btw=False)

        entry_id = self._store.add_pending(self._conversation_id, question)

        return BtwResult(
            is_btw=True,
            question=question,
            entry_id=entry_id,
        )

    async def resolve(self, entry_id: str, response: str) -> None:
        """Resolve a BTW entry with the agent's response."""
        self._store.resolve(self._conversation_id, entry_id, response)

    async def fail(self, entry_id: str, error: str) -> None:
        """Mark a BTW entry as failed."""
        self._store.fail(self._conversation_id, entry_id, error)

    def get_entries(self) -> list[BtwEntry]:
        """Get all BTW entries for the current conversation."""
        return self._store.get_entries(self._conversation_id)

    def dismiss(self, entry_id: str) -> None:
        """Dismiss a BTW entry."""
        self._store.dismiss(self._conversation_id, entry_id)
