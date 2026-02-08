"""Token streaming handler for the TUI.

This module provides a simple token streaming handler that writes
streamed LLM tokens to the TUI's visualizer widget.
"""

import logging
from collections.abc import Callable

from openhands.sdk.llm.streaming import LLMStreamChunk
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


logger = logging.getLogger(__name__)


class TUITokenStreamer:
    """Handles token streaming for the TUI visualizer.

    This class receives streaming token chunks from the LLM and writes
    them to the TUI's visualizer widget for real-time display.

    Note: The caller should call `reset()` before starting a new streaming
    response to ensure header state is properly reset.
    """

    def __init__(
        self,
        visualizer: ConversationVisualizer,
        write_callback: Callable[[str], None] | None = None,
    ):
        """Initialize the token streamer.

        Args:
            visualizer: The TUI visualizer (stored for future extensions).
            write_callback: Callback to write text to the UI. If not provided,
                           streaming tokens will be silently discarded. This is
                           acceptable as the visualizer will still receive
                           complete events through the normal event callback.
        """
        self.visualizer = visualizer
        self._write_callback = write_callback
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

        Args:
            chunk: The streaming chunk containing token deltas.
        """
        try:
            for choice in chunk.choices:
                delta = getattr(choice, "delta", None)
                if not delta:
                    continue

                choice_index = getattr(choice, "index", 0) or 0

                # Only process content from choice.index == 0
                # to avoid interleaving from multiple choices
                if choice_index != 0:
                    continue

                # Handle reasoning content (thinking/CoT)
                reasoning = getattr(delta, "reasoning_content", None)
                if isinstance(reasoning, str) and reasoning.strip():
                    if not self._reasoning_header_emitted:
                        self._reasoning_header_emitted = True
                        reasoning = "💭 Thinking:\n" + reasoning
                    self._write_text(reasoning)

                # Handle regular content
                content = getattr(delta, "content", None)
                if isinstance(content, str) and content:
                    self._write_text(content)

        except Exception as e:
            # Log streaming errors but don't disrupt the UI
            logger.debug("Token streaming error: %s", e)

    def _write_text(self, text: str) -> None:
        """Write text to the UI.

        Args:
            text: The text to write.
        """
        if self._write_callback:
            self._write_callback(text)
        # Note: Without a callback, tokens are discarded but the visualizer
        # will still receive complete events through the normal callback.
