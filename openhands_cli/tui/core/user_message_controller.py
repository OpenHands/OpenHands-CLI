"""UserMessageController - handles sending user input into a conversation."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable

    from openhands_cli.tui.core.conversation_runner import ConversationRunner
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
        """Handle a user-initiated message (starts a new user turn).

        Note: The refinement iteration counter is reset by ConversationManager
        before calling this method. For system-generated refinement messages,
        use handle_refinement_message() instead.

        Args:
            content: The user's message content.
            image_data: Optional image data bytes from clipboard.
        """
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
            runner.visualizer.render_user_message(display_text, image_data=image_data)
        else:
            runner.visualizer.render_user_message(content)

        # Update conversation title (for history panel)
        self._state.set_conversation_title(content or "[Image message]")

        await self._process_message(runner, content, image_data=image_data)

    async def handle_refinement_message(self, content: str) -> None:
        """Handle a system-generated refinement message.

        Unlike handle_user_message(), this does NOT reset the refinement
        iteration counter or update the conversation title. This allows
        the iterative refinement loop to track progress correctly.

        Args:
            content: The refinement message content.
        """
        # Guard: no conversation_id means switching in progress
        if self._state.conversation_id is None:
            return

        runner = self._runners.get_or_create(self._state.conversation_id)

        # Render refinement message - preserves the iteration counter
        runner.visualizer.render_refinement_message(content)

        # Note: Don't update conversation title for refinement messages

        await self._process_message(runner, content)

    async def _process_message(
        self,
        runner: ConversationRunner,
        content: str,
        *,
        image_data: bytes | None = None,
    ) -> None:
        """Process a message by queuing or starting a new run.

        Args:
            runner: The conversation runner to use.
            content: The message content to process.
            image_data: Optional image data bytes from clipboard.
        """

        if runner.is_running:
            await runner.queue_message(content, image_data=image_data)
            return

        self._run_worker(
            runner.process_message_async(
                content, self._headless_mode, image_data=image_data
            ),
            name="process_message",
        )
