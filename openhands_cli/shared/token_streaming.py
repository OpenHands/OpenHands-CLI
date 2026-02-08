"""Shared token streaming utilities.

This module provides common token parsing logic and constants used by both
ACP and TUI token streaming implementations.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from openhands.sdk.llm.streaming import LLMStreamChunk


logger = logging.getLogger(__name__)

# Formatting constants for consistent headers across streaming and non-streaming modes
REASONING_HEADER = "**Reasoning**:\n"


@dataclass
class StreamingContent:
    """Extracted content from a streaming chunk."""

    reasoning: str | None = None
    content: str | None = None


def extract_streaming_content(chunk: LLMStreamChunk) -> StreamingContent:
    """Extract reasoning and content from a streaming chunk.

    Only processes content from choice.index == 0 to avoid interleaving
    from multiple choices (standard streaming uses n=1).

    Args:
        chunk: The streaming chunk from the LLM.

    Returns:
        StreamingContent with reasoning and/or content text (either may be None).
    """
    for choice in chunk.choices:
        delta = getattr(choice, "delta", None)
        if not delta:
            continue

        choice_index = getattr(choice, "index", 0) or 0
        if choice_index != 0:
            continue

        reasoning = getattr(delta, "reasoning_content", None)
        content = getattr(delta, "content", None)

        reasoning_text = None
        if isinstance(reasoning, str) and reasoning.strip():
            reasoning_text = reasoning

        content_text = None
        if isinstance(content, str) and content:
            content_text = content

        return StreamingContent(reasoning=reasoning_text, content=content_text)

    return StreamingContent()


def schedule_threadsafe(
    callback: Callable[[], None],
    loop: asyncio.AbstractEventLoop | None,
) -> None:
    """Schedule a callback to run on the event loop, thread-safe.

    This is the pattern used by ACP for safe UI updates from LLM streaming threads.

    Args:
        callback: The callback to schedule (should be a sync function).
        loop: The event loop to schedule on. If None, callback is called directly.
    """
    if loop is None:
        callback()
        return

    async def _async_wrapper() -> None:
        callback()

    if loop.is_running():
        asyncio.run_coroutine_threadsafe(_async_wrapper(), loop)
    else:
        loop.run_until_complete(_async_wrapper())
