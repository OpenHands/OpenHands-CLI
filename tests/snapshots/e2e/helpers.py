"""Helper utilities for E2E snapshot tests.

Provides scalable waiting mechanisms for Textual apps instead of
repeated pilot.pause() calls.
"""

import asyncio
from typing import TYPE_CHECKING

from textual.widgets import TextArea


if TYPE_CHECKING:
    from textual.pilot import Pilot


def disable_cursor_blink(pilot: "Pilot") -> None:
    """Disable cursor blinking on all TextArea widgets for deterministic snapshots.

    The cursor blink state varies depending on timing, causing flaky snapshot tests.
    This function finds all TextArea widgets and disables blinking while keeping
    the cursor visible.

    Args:
        pilot: The Textual pilot instance
    """
    for widget in pilot.app.query(TextArea):
        widget.cursor_blink = False
        widget._cursor_visible = True


async def wait_for_app_ready(pilot: "Pilot") -> None:
    """Wait for app to be fully initialized and ready.

    This waits for any scheduled animations to complete, which indicates
    the app has finished processing events and rendering.

    Args:
        pilot: The Textual pilot instance
    """
    await pilot.wait_for_scheduled_animations()
    # Disable cursor blinking for deterministic snapshots
    disable_cursor_blink(pilot)


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
    except TimeoutError:
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
