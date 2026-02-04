"""ConversationSwitchController - orchestrates switching between conversations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from openhands_cli.tui.core.events import RequestSwitchConfirmation


if TYPE_CHECKING:
    from collections.abc import Callable

    from textual.message import Message as TextualMessage

    from openhands_cli.tui.core.runner_registry import RunnerRegistry
    from openhands_cli.tui.core.state import ConversationContainer


class ConversationSwitchController:
    def __init__(
        self,
        *,
        state: ConversationContainer,
        runners: RunnerRegistry,
        notify: Callable[..., None],
        post_message: Callable[[TextualMessage], bool],
        run_worker: Callable[..., object],
        call_from_thread: Callable[..., None],
    ) -> None:
        self._state = state
        self._runners = runners
        self._notify = notify
        self._post_message = post_message
        self._run_worker = run_worker
        self._call_from_thread = call_from_thread

    def request_switch(self, target_id: uuid.UUID) -> None:
        if self._state.conversation_id == target_id:
            self._notify(
                "This conversation is already active.",
                title="Already Active",
                severity="information",
            )
            return

        if self._state.running:
            self._post_message(RequestSwitchConfirmation(target_id))
            return

        self._perform_switch(target_id, pause_current=False)

    def handle_switch_confirmed(self, target_id: uuid.UUID, *, confirmed: bool) -> None:
        if confirmed:
            self._perform_switch(target_id, pause_current=True)

    def _perform_switch(self, target_id: uuid.UUID, *, pause_current: bool) -> None:
        # Disable input and mark switching in progress.
        self._state.start_switching()

        def worker() -> None:
            if pause_current:
                runner = self._runners.current
                if runner is not None and runner.is_running:
                    runner.conversation.pause()

            self._call_from_thread(self._prepare_switch, target_id)

        self._run_worker(
            worker,
            name="switch_conversation",
            group="switch_conversation",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _prepare_switch(self, target_id: uuid.UUID) -> None:
        # Reset for new conversation (conversation_id remains None until finish).
        self._state.reset_conversation_state()

        self._runners.clear_current()
        self._runners.get_or_create(target_id)

        self._state.finish_switching(target_id)

        self._notify(
            f"Resumed conversation {target_id.hex[:8]}",
            title="Switched",
            severity="information",
        )
