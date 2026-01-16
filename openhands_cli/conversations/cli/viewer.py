"""Viewer for conversation trajectories."""

from __future__ import annotations

from rich.console import Console

from openhands.sdk.conversation.visualizer import DefaultConversationVisualizer
from openhands.tools.preset.default import register_default_tools
from openhands_cli.conversations.store.local import LocalFileStore
from openhands_cli.theme import OPENHANDS_THEME


# Register default tools to ensure all Action subclasses are available
# for proper deserialization of events
register_default_tools()

console = Console()


class ConversationViewer:
    """Class for viewing conversation trajectories."""

    def __init__(self):
        """Initialize the conversation viewer."""
        self.store = LocalFileStore()

    def view(self, conversation_id: str, limit: int = 20) -> bool:
        """View events from a conversation.

        Args:
            conversation_id: The ID of the conversation to view.
            limit: Maximum number of events to display.

        Returns:
            True if the conversation was found and displayed, False otherwise.
        """
        if not self.store.exists(conversation_id):
            console.print(
                f"Conversation not found: {conversation_id}",
                style=OPENHANDS_THEME.error,
            )
            return False

        events_iterator = self.store.load_events(conversation_id)

        # Create visualizer
        visualizer = DefaultConversationVisualizer()

        # Display header
        console.print(
            f"Conversation: {conversation_id}",
            style=f"{OPENHANDS_THEME.primary} bold",
        )
        console.print("-" * 80, style=f"{OPENHANDS_THEME.secondary} dim")
        console.print()

        # Load and display events
        events_displayed = 0
        try:
            for i, event in enumerate(events_iterator):
                if i >= limit:
                    break
                visualizer.on_event(event)
                events_displayed += 1
        except Exception as e:
            console.print(
                f"Error loading events: {e}",
                style=OPENHANDS_THEME.error,
            )

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
