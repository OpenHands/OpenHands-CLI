"""Helper utilities for E2E snapshot tests.

Provides scalable waiting mechanisms for Textual apps instead of
repeated pilot.pause() calls.
"""

import asyncio
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from textual.pilot import Pilot
    from textual.widget import Widget

_W = TypeVar("_W", bound="Widget")


async def wait_for_app_ready(pilot: "Pilot") -> None:
    """Wait for app to be fully initialized and ready.

    This waits for any scheduled animations to complete, which indicates
    the app has finished processing events and rendering.

    Args:
        pilot: The Textual pilot instance
    """
    await pilot.wait_for_scheduled_animations()


async def wait_for_widget(
    pilot: "Pilot",
    widget_type: type[_W],
    timeout: float = 5.0,
) -> _W:
    """Wait for a specific widget type to be available in the app.

    Args:
        pilot: The Textual pilot instance
        widget_type: The widget class to look for
        timeout: Maximum time to wait in seconds

    Returns:
        The widget instance

    Raises:
        TimeoutError: If widget is not found within timeout
    """
    start = asyncio.get_event_loop().time()
    while True:
        await pilot.wait_for_scheduled_animations()
        try:
            widget = pilot.app.query_one(widget_type)
            return widget
        except Exception:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Widget {widget_type.__name__} not found after {timeout}s"
                )
            await pilot.pause()


async def wait_for_idle(pilot: "Pilot", timeout: float = 30.0) -> None:
    """Wait for the app to become idle (no pending animations or workers).

    This waits for:
    1. All background workers to complete
    2. All scheduled animations to finish

    This is useful after triggering an action to wait for all resulting
    processing and UI updates to complete.

    Args:
        pilot: The Textual pilot instance
        timeout: Maximum time to wait for workers in seconds
    """
    # Wait for all workers (background tasks) to complete
    try:
        await asyncio.wait_for(
            pilot.app.workers.wait_for_complete(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        pass

    # Then wait for any animations triggered by worker completion
    await pilot.wait_for_scheduled_animations()


async def type_text(pilot: "Pilot", text: str) -> None:
    """Type text character by character.

    Args:
        pilot: The Textual pilot instance
        text: The text to type
    """
    for char in text:
        await pilot.press(char)
