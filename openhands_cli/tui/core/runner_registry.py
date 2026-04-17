"""RunnerRegistry - owns ConversationRunner instances and background warmup."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from textual.message_pump import MessagePump

from openhands_cli.locations import get_work_dir
from openhands_cli.tui.content.resources import collect_loaded_resources
from openhands_cli.tui.core.events import (
    ConversationWarmupCompleted,
    ConversationWarmupFailed,
)


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
        run_worker: Callable[..., object],
        call_from_thread: Callable[..., None],
    ) -> None:
        self._factory = factory
        self._state = state
        self._message_pump = message_pump
        self._notification_callback = notification_callback
        self._run_worker = run_worker
        self._call_from_thread = call_from_thread
        self._runners: dict[uuid.UUID, ConversationRunner] = {}
        self._current_runner: ConversationRunner | None = None
        self._warming_conversations: set[uuid.UUID] = set()
        self._pending_messages: dict[uuid.UUID, list[str]] = {}

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

    def is_warming(self, conversation_id: uuid.UUID) -> bool:
        return conversation_id in self._warming_conversations

    def enqueue_pending_message(self, conversation_id: uuid.UUID, content: str) -> None:
        self._pending_messages.setdefault(conversation_id, []).append(content)

    def pop_pending_messages(self, conversation_id: uuid.UUID) -> list[str]:
        return self._pending_messages.pop(conversation_id, [])

    def start_prewarm(self, conversation_id: uuid.UUID) -> None:
        runner = self.get_or_create(conversation_id)
        if runner.is_ready:
            self._post_warmup_completed(conversation_id, runner)
            return

        if conversation_id in self._warming_conversations:
            return

        self._warming_conversations.add(conversation_id)
        self._state.set_startup_status(
            "Preparing conversation tools in the background…"
        )

        def worker() -> None:
            try:
                runner.ensure_initialized()
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                self._dispatch_to_main_thread(
                    self._handle_warmup_failure, conversation_id, error_message
                )
                return

            self._dispatch_to_main_thread(
                self._post_warmup_completed, conversation_id, runner
            )

        self._run_worker(
            worker,
            name=f"warmup_{conversation_id.hex[:8]}",
            group=f"warmup_{conversation_id}",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _dispatch_to_main_thread(
        self, callback: Callable[..., None], *args: object
    ) -> None:
        if threading.current_thread() is threading.main_thread():
            callback(*args)
        else:
            self._call_from_thread(callback, *args)

    def _post_warmup_completed(
        self, conversation_id: uuid.UUID, runner: ConversationRunner
    ) -> None:
        self._warming_conversations.discard(conversation_id)
        if runner.conversation is None:
            return

        agent = getattr(runner.conversation, "agent", None)
        loaded_resources = collect_loaded_resources(
            agent=agent,
            working_dir=get_work_dir(),
        )
        has_critic = bool(getattr(agent, "critic", None))
        self._message_pump.post_message(
            ConversationWarmupCompleted(
                conversation_id=conversation_id,
                has_critic=has_critic,
                loaded_resources=loaded_resources,
            )
        )

    def _handle_warmup_failure(self, conversation_id: uuid.UUID, error: str) -> None:
        self._warming_conversations.discard(conversation_id)
        self._message_pump.post_message(
            ConversationWarmupFailed(conversation_id=conversation_id, error=error)
        )
