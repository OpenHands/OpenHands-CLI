"""BTW (By The Way) interceptor for handling side-channel questions.

This module provides a function that intercepts /btw commands and routes them
through the ask_agent side-channel without disrupting the main task flow.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any


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

    This interceptor checks if a message starts with /btw and if so,
    handles it as a side-channel question instead of a regular message.
    """

    def __init__(
        self,
        conversation_id: str | None,
        ask_agent_callback: Callable[[str, str], Any],
        get_btw_store: Callable[[], Any],
    ) -> None:
        """Initialize the BTW interceptor.

        Args:
            conversation_id: The current conversation ID.
            ask_agent_callback: Callback to call the ask_agent API.
            get_btw_store: Function to get the BTW store.
        """
        self._conversation_id = conversation_id
        self._ask_agent_callback = ask_agent_callback
        self._get_btw_store = get_btw_store

    def set_conversation_id(self, conversation_id: str | None) -> None:
        """Update the conversation ID.

        Args:
            conversation_id: The new conversation ID.
        """
        self._conversation_id = conversation_id

    def process(self, message: str) -> BtwResult:
        """Process a message to check if it's a BTW command.

        Args:
            message: The user's message.

        Returns:
            BtwResult indicating if it's a BTW command and details.
        """
        trimmed = message.strip()
        is_btw = trimmed == BTW_COMMAND or trimmed.startswith(BTW_PREFIX)

        # If no conversation ID or not a BTW command, passthrough
        if not self._conversation_id or not is_btw:
            return BtwResult(is_btw=False)

        # Extract the question
        question = trimmed[len(BTW_COMMAND) :].strip()
        if not question:
            # /btw with no question - ignore
            return BtwResult(is_btw=False)

        # Add pending entry to store
        store = self._get_btw_store()
        entry_id = store.add_pending(self._conversation_id, question)

        return BtwResult(
            is_btw=True,
            question=question,
            entry_id=entry_id,
        )

    async def resolve(self, entry_id: str, response: str) -> None:
        """Resolve a BTW entry with the agent's response.

        Args:
            entry_id: The entry ID to resolve.
            response: The agent's response.
        """
        store = self._get_btw_store()
        store.resolve(self._conversation_id, entry_id, response)

    async def fail(self, entry_id: str, error: str) -> None:
        """Mark a BTW entry as failed.

        Args:
            entry_id: The entry ID that failed.
            error: The error message.
        """
        store = self._get_btw_store()
        store.fail(self._conversation_id, entry_id, error)

    def get_entries(self) -> list[BtwEntry]:
        """Get all BTW entries for the current conversation.

        Returns:
            List of BTW entries.
        """
        store = self._get_btw_store()
        return store.get_entries(self._conversation_id)

    def dismiss(self, entry_id: str) -> None:
        """Dismiss a BTW entry.

        Args:
            entry_id: The entry ID to dismiss.
        """
        store = self._get_btw_store()
        store.dismiss(self._conversation_id, entry_id)
