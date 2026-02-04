"""UserMessageController - handles sending user input into a conversation."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable

    from openhands_cli.tui.core.runner_registry import RunnerRegistry
    from openhands_cli.tui.core.state import ConversationContainer


class UserMessageController:
    def __init__(
        self,
        *,
        state: ConversationContainer,
        runners: RunnerRegistry,
        run_worker: Callable[..., object],
        headless_mode: bool,
    ) -> None:
        self._state = state
        self._runners = runners
        self._run_worker = run_worker
        self._headless_mode = headless_mode

    async def handle_user_message(self, content: str) -> None:
        # Guard: no conversation_id means switching in progress
        if self._state.conversation_id is None:
            return

        runner = self._runners.get_or_create(self._state.conversation_id)

        # Render user message (also dismisses pending feedback widgets)
        runner.visualizer.render_user_message(content)

        # Update conversation title (for history panel)
        self._state.set_conversation_title(content)

        if runner.is_running:
            await runner.queue_message(content)
            return

        self._run_worker(
            runner.process_message_async(content, self._headless_mode),
            name="process_message",
        )
