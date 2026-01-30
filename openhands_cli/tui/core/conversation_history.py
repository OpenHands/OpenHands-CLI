"""Conversation history state and pagination.

This module manages the state of a single conversation's event history
for rendering in the UI. Supports pagination (loading N events at a time)
for long histories.

Note: This is about events within ONE conversation, not the list of all
conversations (which is handled by HistorySidePanel).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from openhands.sdk.event.base import Event
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


# Default number of events to render initially and on each page
DEFAULT_PAGE_SIZE = 5


@dataclass
class ConversationHistoryState:
    """Tracks pagination state for a single conversation's event history."""

    events: list[Any] = field(default_factory=list)  # list[Event] but Any for tests
    rendered_count: int = 0
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def has_more(self) -> bool:
        """Check if there are more events to render."""
        return self.rendered_count < len(self.events)

    @property
    def remaining_count(self) -> int:
        """Number of events not yet rendered."""
        return len(self.events) - self.rendered_count

    def get_next_page(self) -> list[Event]:
        """Get the next page of events to render.

        Returns events in chronological order (oldest first within the page),
        but pages are loaded from newest to oldest.
        """
        if not self.has_more:
            return []

        # Calculate the range of events to return
        # Events are stored oldest-first, but we want to show newest first
        # So we take from the end of the unrendered portion
        end_idx = len(self.events) - self.rendered_count
        start_idx = max(0, end_idx - self.page_size)

        # Get the page (will be in chronological order)
        page = self.events[start_idx:end_idx]

        # Update rendered count
        self.rendered_count += len(page)

        return page

    def get_initial_page(self) -> list[Event]:
        """Get the initial page of events (most recent).

        This is called when first loading a conversation to show
        the last N events.
        """
        if not self.events:
            return []

        # Take the last page_size events
        page = self.events[-self.page_size :]

        # Update rendered count
        self.rendered_count = len(page)

        return page


def render_events_to_visualizer(
    events: Sequence[Any],
    visualizer: ConversationVisualizer,
) -> None:
    """Render a list of events through the visualizer."""
    for event in events:
        # The visualizer's on_event handles thread safety internally
        visualizer.on_event(event)


def create_conversation_history_state(
    events: Sequence[Any],
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ConversationHistoryState:
    """Create a new state for rendering a conversation's event history."""
    return ConversationHistoryState(
        events=list(events),  # Copy to avoid mutation
        rendered_count=0,
        page_size=page_size,
    )
