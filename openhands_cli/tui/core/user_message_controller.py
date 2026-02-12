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

    async def handle_user_message(
        self, content: str, *, image_data: bytes | None = None
    ) -> None:
        # Guard: no conversation_id means switching in progress
        if self._state.conversation_id is None:
            return

        runner = self._runners.get_or_create(self._state.conversation_id)

        # Render user message (also dismisses pending feedback widgets)
        if image_data:
            from openhands_cli.tui.utils.clipboard_image import (
                get_image_dimensions,
                get_image_size_display,
            )

            size_str = get_image_size_display(image_data)
            dims = get_image_dimensions(image_data)
            dims_str = f"{dims[0]}x{dims[1]}, " if dims else ""
            display_text = (
                f"{content}\n[Image: {dims_str}{size_str}]"
                if content
                else f"[Image: {dims_str}{size_str}]"
            )
            runner.visualizer.render_user_message(
                display_text, image_data=image_data
            )
        else:
            runner.visualizer.render_user_message(content)

        # Update conversation title (for history panel)
        self._state.set_conversation_title(content or "[Image message]")

        if runner.is_running:
            await runner.queue_message(content, image_data=image_data)
            return

        self._run_worker(
            runner.process_message_async(
                content, self._headless_mode, image_data=image_data
            ),
            name="process_message",
        )
