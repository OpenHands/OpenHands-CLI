"""Token streaming handler for the TUI.

This module provides a token streaming handler that writes streamed LLM tokens
to the TUI's visualizer widget, using shared utilities with ACP for consistency.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from openhands.sdk.llm.streaming import LLMStreamChunk
from openhands_cli.shared.token_streaming import (
    REASONING_HEADER,
    extract_streaming_content,
    schedule_threadsafe,
)
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


logger = logging.getLogger(__name__)


class TUITokenStreamer:
    """Handles token streaming for the TUI visualizer.

    This class receives streaming token chunks from the LLM and writes
    them to the TUI's visualizer widget for real-time display.

    Uses the same token parsing logic as ACP's TokenBasedEventSubscriber
    for consistency, and schedules UI updates thread-safely.

    Note: The caller should call `reset()` before starting a new streaming
    response to ensure header state is properly reset.
    """

    def __init__(
        self,
        visualizer: ConversationVisualizer,
        write_callback: Callable[[str], None] | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        """Initialize the token streamer.

        Args:
            visualizer: The TUI visualizer (stored for future extensions).
            write_callback: Callback to write text to the UI. If not provided,
                           streaming tokens will be silently discarded. This is
                           acceptable as the visualizer will still receive
                           complete events through the normal event callback.
            loop: Event loop for thread-safe scheduling. If provided, callbacks
                  are scheduled via run_coroutine_threadsafe (like ACP does).
                  If None, callbacks are invoked directly (caller must ensure
                  thread safety).
        """
        self.visualizer = visualizer
        self._write_callback = write_callback
        self._loop = loop
        self._reasoning_header_emitted = False

    def reset(self) -> None:
        """Reset state for a new streaming response.

        Call this before starting a new streaming response to ensure
        the reasoning header is emitted again.
        """
        self._reasoning_header_emitted = False

    def on_token(self, chunk: LLMStreamChunk) -> None:
        """Handle a streaming token chunk.

        This callback is invoked for each token delta from the LLM.
        Uses shared token parsing logic for consistency with ACP.

        Args:
            chunk: The streaming chunk containing token deltas.
        """
        try:
            # Use shared parsing logic (same as ACP)
            streaming = extract_streaming_content(chunk)

            # Handle reasoning content (thinking/CoT)
            if streaming.reasoning:
                text = streaming.reasoning
                if not self._reasoning_header_emitted:
                    self._reasoning_header_emitted = True
                    text = REASONING_HEADER + text
                self._schedule_write(text)

            # Handle regular content
            if streaming.content:
                self._schedule_write(streaming.content)

        except Exception as e:
            logger.warning("Token streaming error: %s", e, exc_info=True)

    def _schedule_write(self, text: str) -> None:
        """Schedule a write to the UI, thread-safe.

        Uses the same pattern as ACP's _schedule_update for safe UI updates
        from LLM streaming threads.

        Args:
            text: The text to write.
        """
        if not self._write_callback:
            return

        def do_write() -> None:
            if self._write_callback:
                self._write_callback(text)

        schedule_threadsafe(do_write, self._loop)
