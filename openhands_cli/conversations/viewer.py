"""Viewer for conversation trajectories."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter
from rich.console import Console

from openhands.sdk.conversation.visualizer import DefaultConversationVisualizer
from openhands.sdk.event.base import Event
from openhands.tools.preset.default import register_default_tools
from openhands_cli.locations import CONVERSATIONS_DIR
from openhands_cli.theme import OPENHANDS_THEME


# Register default tools to ensure all Action subclasses are available
# for proper deserialization of events
register_default_tools()

console = Console()


class ConversationViewer:
    """Class for viewing conversation trajectories."""

    def __init__(self):
        """Initialize the conversation viewer."""
        self.conversations_dir = CONVERSATIONS_DIR
        self._event_adapter = TypeAdapter(Event)

    def view(self, conversation_id: str, limit: int = 20) -> bool:
        """View events from a conversation.

        Args:
            conversation_id: The ID of the conversation to view.
            limit: Maximum number of events to display.

        Returns:
            True if the conversation was found and displayed, False otherwise.
        """
        conversation_path = Path(self.conversations_dir) / conversation_id
        events_dir = conversation_path / "events"

        if not conversation_path.exists():
            console.print(
                f"Conversation not found: {conversation_id}",
                style=OPENHANDS_THEME.error,
            )
            return False

        if not events_dir.exists() or not events_dir.is_dir():
            console.print(
                f"No events found for conversation: {conversation_id}",
                style=OPENHANDS_THEME.error,
            )
            return False

        # Get all event files and sort them
        event_files = list(events_dir.glob("event-*.json"))
        if not event_files:
            console.print(
                f"No events found for conversation: {conversation_id}",
                style=OPENHANDS_THEME.warning,
            )
            return False

        # Sort event files by name to get them in order
        event_files.sort()

        # Limit the number of events
        event_files = event_files[:limit]

        # Create visualizer
        visualizer = DefaultConversationVisualizer()

        # Display header
        console.print(
            f"Conversation: {conversation_id}",
            style=f"{OPENHANDS_THEME.primary} bold",
        )
        console.print(
            f"Showing {len(event_files)} event(s)",
            style=f"{OPENHANDS_THEME.secondary} dim",
        )
        console.print("-" * 80, style=f"{OPENHANDS_THEME.secondary} dim")
        console.print()

        # Load and display each event
        events_displayed = 0
        for event_file in event_files:
            event = self._load_event(event_file)
            if event is not None:
                visualizer.on_event(event)
                events_displayed += 1

        if events_displayed == 0:
            console.print(
                "No valid events could be displayed.",
                style=OPENHANDS_THEME.warning,
            )
            return False

        console.print()
        console.print("-" * 80, style=f"{OPENHANDS_THEME.secondary} dim")
        console.print(
            f"Displayed {events_displayed} event(s)",
            style=f"{OPENHANDS_THEME.secondary} dim",
        )

        return True

    def _load_event(self, event_file: Path) -> Event | None:
        """Load an event from a JSON file.

        Args:
            event_file: Path to the event JSON file.

        Returns:
            The parsed Event object, or None if parsing failed.
        """
        try:
            with open(event_file, encoding="utf-8") as f:
                event_data = json.load(f)
            return self._event_adapter.validate_python(event_data)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            console.print(
                f"Warning: Could not parse event file {event_file.name}: {e}",
                style=OPENHANDS_THEME.warning,
            )
            return None


def view_conversation(conversation_id: str, limit: int = 20) -> bool:
    """View events from a conversation.

    Args:
        conversation_id: The ID of the conversation to view.
        limit: Maximum number of events to display.

    Returns:
        True if the conversation was found and displayed, False otherwise.
    """
    viewer = ConversationViewer()
    return viewer.view(conversation_id, limit)
