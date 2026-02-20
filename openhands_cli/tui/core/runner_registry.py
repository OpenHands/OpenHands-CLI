"""RunnerRegistry - owns ConversationRunner instances and current runner."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from textual.message_pump import MessagePump


if TYPE_CHECKING:
    from openhands_cli.tui.core.conversation_runner import ConversationRunner
    from openhands_cli.tui.core.runner_factory import (
        NotificationCallback,
        RunnerFactory,
    )
    from openhands_cli.tui.core.state import ConversationContainer


class RunnerRegistry:
    def __init__(
        self,
        *,
        factory: RunnerFactory,
        state: ConversationContainer,
        message_pump: MessagePump,
        notification_callback: NotificationCallback,
    ) -> None:
        self._factory = factory
        self._state = state
        self._message_pump = message_pump
        self._notification_callback = notification_callback
        self._runners: dict[uuid.UUID, ConversationRunner] = {}
        self._current_runner: ConversationRunner | None = None

    @property
    def current(self) -> ConversationRunner | None:
        return self._current_runner

    def clear_current(self) -> None:
        self._current_runner = None

    def get_or_create(self, conversation_id: uuid.UUID) -> ConversationRunner:
        runner = self._runners.get(conversation_id)
        if runner is None:
            runner = self._factory.create(
                conversation_id,
                message_pump=self._message_pump,
                notification_callback=self._notification_callback,
            )
            self._runners[conversation_id] = runner

        if runner.conversation is not None:
            self._state.attach_conversation_state(runner.conversation.state)

        self._current_runner = runner
        return runner
