"""History replay with pagination for conversation UI.

This module handles replaying conversation history when switching to an existing
conversation. It supports pagination (loading N events at a time) and scroll-based
loading for better UX with long histories.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from openhands.sdk.event.base import Event
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


# Default number of events to load initially and on each scroll-up
DEFAULT_PAGE_SIZE = 5


@dataclass
class HistoryReplayState:
    """Tracks the state of history replay for a conversation.

    Attributes:
        events: Full list of events from conversation history.
        displayed_count: Number of events currently displayed in UI.
        page_size: Number of events to load per page.
    """

    events: list[Any] = field(default_factory=list)  # list[Event] but Any for tests
    displayed_count: int = 0
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def has_more(self) -> bool:
        """Check if there are more events to load."""
        return self.displayed_count < len(self.events)

    @property
    def remaining_count(self) -> int:
        """Number of events not yet displayed."""
        return len(self.events) - self.displayed_count

    def get_next_page(self) -> list[Event]:
        """Get the next page of events to display.

        Returns events in chronological order (oldest first within the page),
        but pages are loaded from newest to oldest.

        Returns:
            List of events for the next page, or empty list if no more.
        """
        if not self.has_more:
            return []

        # Calculate the range of events to return
        # Events are stored oldest-first, but we want to show newest first
        # So we take from the end of the undisplayed portion
        end_idx = len(self.events) - self.displayed_count
        start_idx = max(0, end_idx - self.page_size)

        # Get the page (will be in chronological order)
        page = self.events[start_idx:end_idx]

        # Update displayed count
        self.displayed_count += len(page)

        return page

    def get_initial_page(self) -> list[Event]:
        """Get the initial page of events (most recent).

        This is called when first loading a conversation to show
        the last N events.

        Returns:
            List of the most recent events up to page_size.
        """
        if not self.events:
            return []

        # Take the last page_size events
        page = self.events[-self.page_size :]

        # Update displayed count
        self.displayed_count = len(page)

        return page


def replay_events_to_visualizer(
    events: Sequence[Any],
    visualizer: ConversationVisualizer,
) -> None:
    """Replay a list of events through the visualizer.

    This renders each event in the UI using the visualizer's on_event method.
    The visualizer handles thread safety internally via _run_on_main_thread.

    Args:
        events: List of events to replay (in chronological order).
        visualizer: The ConversationVisualizer to render events.
    """
    for event in events:
        # The visualizer's on_event handles thread safety internally
        visualizer.on_event(event)


def create_history_state(
    events: Sequence[Any],
    page_size: int = DEFAULT_PAGE_SIZE,
) -> HistoryReplayState:
    """Create a new history replay state from conversation events.

    Args:
        events: Full list of events from conversation history.
        page_size: Number of events to load per page.

    Returns:
        HistoryReplayState ready for pagination.
    """
    return HistoryReplayState(
        events=list(events),  # Copy to avoid mutation
        displayed_count=0,
        page_size=page_size,
    )
