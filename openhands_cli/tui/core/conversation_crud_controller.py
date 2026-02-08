"""ConversationCrudController - create new conversations and reset state."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID


if TYPE_CHECKING:
    from collections.abc import Callable

    from openhands_cli.conversations.protocols import ConversationStore
    from openhands_cli.tui.core.runner_registry import RunnerRegistry
    from openhands_cli.tui.core.state import ConversationContainer


class ConversationCrudController:
    def __init__(
        self,
        *,
        state: ConversationContainer,
        store: ConversationStore,
        runners: RunnerRegistry,
        notify: Callable[..., None],
    ) -> None:
        self._state = state
        self._store = store
        self._runners = runners
        self._notify = notify

    def create_conversation(self) -> None:
        if self._state.running:
            self._notify(
                "Cannot start a new conversation while one is running. "
                "Please wait for the current conversation to complete or pause it.",
                title="New Conversation Error",
                severity="error",
            )
            return

        new_id = self._store.create()

        self._runners.clear_current()

        # Reset state - triggers reactive UI updates
        self._state.reset_conversation_state()
        self._state.conversation_id = UUID(new_id)

        self._notify(
            "Started a new conversation",
            title="New Conversation",
            severity="information",
        )
