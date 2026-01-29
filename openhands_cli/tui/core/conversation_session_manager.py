"""Conversation session manager.

Manages conversation sessions and cached panes for fast switching.
Supports multiple concurrent sessions for multi-thread chat support.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openhands_cli.tui.core.conversation_runner import ConversationRunner


if TYPE_CHECKING:
    from openhands_cli.tui.panels.conversation_pane import ConversationPane


@dataclass
class ConversationSession:
    """Holds per-conversation runtime state."""

    conversation_id: uuid.UUID
    runner: ConversationRunner | None = None
    pane: ConversationPane | None = None
    task: asyncio.Task | None = None


class ConversationSessionManager:
    """Manages conversation sessions with pane caching (Single Source of Truth).

    Each visited conversation gets its own session with:
    - ConversationRunner (agent interaction)
    - asyncio.Task (background execution)
    - ConversationPane (cached UI with rendered content)

    Pane caching (Flyweight pattern) enables instant switching between conversations
    without reloading events from disk.
    """

    def __init__(self, initial_conversation_id: uuid.UUID) -> None:
        self._sessions: dict[uuid.UUID, ConversationSession] = {}
        self._active_conversation_id = initial_conversation_id

    @property
    def active_conversation_id(self) -> uuid.UUID:
        """Get the currently active conversation ID."""
        return self._active_conversation_id

    @property
    def active_session(self) -> ConversationSession | None:
        """Get the currently active session."""
        return self._sessions.get(self._active_conversation_id)

    def get_session(self, conversation_id: uuid.UUID) -> ConversationSession | None:
        """Get session by conversation ID (may return None if not visited)."""
        return self._sessions.get(conversation_id)

    def get_or_create_session(self, conversation_id: uuid.UUID) -> ConversationSession:
        """Get existing session or create a new one."""
        if conversation_id not in self._sessions:
            self._sessions[conversation_id] = ConversationSession(
                conversation_id=conversation_id
            )
        return self._sessions[conversation_id]

    def set_active_conversation(self, conversation_id: uuid.UUID) -> None:
        """Switch to a different conversation."""
        self._active_conversation_id = conversation_id
        # Ensure session exists
        self.get_or_create_session(conversation_id)

    def set_runner(
        self,
        conversation_id: uuid.UUID,
        runner: ConversationRunner | None,
        task: asyncio.Task | None = None,
    ) -> None:
        """Set the runner and optional background task for a conversation."""
        session = self.get_or_create_session(conversation_id)
        session.runner = runner
        session.task = task

    def set_pane(
        self, conversation_id: uuid.UUID, pane: ConversationPane | None
    ) -> None:
        """Set the cached pane for a conversation."""
        session = self.get_or_create_session(conversation_id)
        session.pane = pane

    def get_pane(self, conversation_id: uuid.UUID) -> ConversationPane | None:
        """Get cached pane for a conversation (None if not cached)."""
        session = self._sessions.get(conversation_id)
        return session.pane if session else None

    def has_cached_pane(self, conversation_id: uuid.UUID) -> bool:
        """Check if a conversation has a cached pane."""
        return self.get_pane(conversation_id) is not None

    def get_runner(self, conversation_id: uuid.UUID) -> ConversationRunner | None:
        """Get cached runner for a conversation (None if not cached)."""
        session = self._sessions.get(conversation_id)
        return session.runner if session else None

    def get_task(self, conversation_id: uuid.UUID) -> asyncio.Task | None:
        """Get background task for a conversation (None if not cached)."""
        session = self._sessions.get(conversation_id)
        return session.task if session else None

    def has_cached_session(self, conversation_id: uuid.UUID) -> bool:
        """Check if conversation has both cached pane and runner."""
        session = self._sessions.get(conversation_id)
        if not session:
            return False
        return session.pane is not None and session.runner is not None

    async def close_all(self) -> None:
        """Cancel all running tasks and clear sessions."""
        for session in self._sessions.values():
            if session.task and not session.task.done():
                session.task.cancel()
                try:
                    await session.task
                except asyncio.CancelledError:
                    pass
        self._sessions.clear()
