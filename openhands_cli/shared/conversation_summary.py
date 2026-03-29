"""Shared utilities for extracting conversation summaries."""

from collections.abc import Iterable

from rich.text import Text

from openhands.sdk.event.base import Event


def extract_conversation_summary(events: Iterable[Event]) -> tuple[int, Text]:
    """Extract a summary from conversation events.

    Iterates through events to count agent messages and find the last
    agent's visualized message.

    Args:
        events: Iterable of conversation events.

    Returns:
        Tuple of (agent_event_count, last_agent_message).
        If no agent messages are found, returns (0, Text("No agent messages found")).
    """
    agent_event_count = 0
    last_agent_message = Text(text="No agent messages found")

    for event in events:
        if event.source == "agent":
            agent_event_count += 1
            last_agent_message = event.visualize

    return agent_event_count, last_agent_message
