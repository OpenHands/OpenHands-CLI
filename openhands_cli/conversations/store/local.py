"""Local file system implementation of ConversationStore."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from openhands.sdk import MessageEvent
from openhands.sdk.event.base import Event

# from openhands.tools.preset.default import register_default_tools (moved to __init__)
from openhands_cli.conversations.models import ConversationMetadata
from openhands_cli.conversations.protocols import ConversationStore
from openhands_cli.locations import get_conversations_dir
from openhands_cli.utils import extract_text_from_message_content


class LocalFileStore(ConversationStore):
    """Local file system implementation of conversation storage."""

    def __init__(self, base_dir: str | None = None) -> None:
        """Initialize the local file store.

        Args:
            base_dir: Base directory for storing conversations.
                Defaults to get_conversations_dir().
        """
        # Register default tools to ensure all Action subclasses are available
        # for proper deserialization of events.
        # Import locally to avoid hard dependency on browser-use at module level.
        from openhands.tools.preset.default import register_default_tools

        register_default_tools(enable_browser=False)
        self.base_dir = Path(
            base_dir if base_dir is not None else get_conversations_dir()
        )
        self._event_adapter = TypeAdapter(Event)

    def list_conversations(self, limit: int = 100) -> list[ConversationMetadata]:
        """List recent conversations."""
        conversations = []

        if not self.base_dir.exists():
            return conversations

        # Iterate through all conversation directories
        for conversation_dir in self.base_dir.iterdir():
            if not conversation_dir.is_dir():
                continue

            metadata = self._parse_conversation_dir(conversation_dir)
            if metadata:
                conversations.append(metadata)

        # Sort by creation date, latest first
        conversations.sort(key=lambda x: x.created_at, reverse=True)
        return conversations[:limit]

    def get_metadata(self, conversation_id: str) -> ConversationMetadata | None:
        """Get metadata for a specific conversation."""
        conversation_dir = self.base_dir / conversation_id
        if not conversation_dir.exists() or not conversation_dir.is_dir():
            return None
        return self._parse_conversation_dir(conversation_dir)

    def get_event_count(self, conversation_id: str) -> int:
        """Get the total number of events in a conversation."""
        conversation_dir = self.base_dir / conversation_id
        events_dir = conversation_dir / "events"

        if not events_dir.exists() or not events_dir.is_dir():
            return 0

        return len(list(events_dir.glob("event-*.json")))

    def load_events(
        self,
        conversation_id: str,
        limit: int | None = None,
        start_from_newest: bool = False,
    ) -> Iterator[Event]:
        """Load events for a conversation."""
        conversation_dir = self.base_dir / conversation_id
        events_dir = conversation_dir / "events"

        if not events_dir.exists() or not events_dir.is_dir():
            return

        # Get all event files and sort them
        event_files = list(events_dir.glob("event-*.json"))
        event_files.sort()

        if limit is not None:
            if start_from_newest:
                event_files = event_files[-limit:]
            else:
                event_files = event_files[:limit]

        for event_file in event_files:
            event = self._load_event_from_file(event_file)
            if event:
                yield event

    def exists(self, conversation_id: str) -> bool:
        """Check if a conversation exists."""
        return (self.base_dir / conversation_id).exists()

    def create(self, conversation_id: str | None = None) -> str:
        """Create a new conversation.

        Args:
            conversation_id: Optional ID for the new conversation.
                           If not provided, one will be generated.

        Returns:
            The conversation ID.
        """
        if not conversation_id:
            conversation_id = uuid.uuid4().hex

        conversation_dir = self.base_dir / conversation_id
        conversation_dir.mkdir(parents=True, exist_ok=True)
        # Create events directory to be ready for writes
        (conversation_dir / "events").mkdir(exist_ok=True)

        return conversation_id

    def _parse_conversation_dir(
        self, conversation_dir: Path
    ) -> ConversationMetadata | None:
        """Parse a single conversation directory."""
        events_dir = conversation_dir / "events"

        # Check if events directory exists
        if not events_dir.exists() or not events_dir.is_dir():
            return None

        # Get all event files
        event_files = list(events_dir.glob("event-*.json"))
        if not event_files:
            return None

        # Sort event files to find the first one
        event_files.sort()
        first_event_file = event_files[0]

        try:
            # Parse the first event file to get timestamp
            with open(first_event_file, encoding="utf-8") as f:
                first_event = json.load(f)

            timestamp_str = first_event.get("timestamp")
            if not timestamp_str:
                return None

            created_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            # Find the first user message for the title
            first_user_prompt = self._find_first_user_prompt(event_files)

            return ConversationMetadata(
                id=conversation_dir.name,
                created_at=created_at,
                title=first_user_prompt,
            )

        except (json.JSONDecodeError, ValueError, KeyError):
            return None

    def _find_first_user_prompt(self, event_files: list[Path]) -> str | None:
        """Find the first user prompt in the conversation events."""
        for event_file in event_files:
            try:
                with open(event_file, encoding="utf-8") as f:
                    event_data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

            message_event = self._to_message_event(event_data)
            if message_event is None or message_event.source != "user":
                continue

            text = extract_text_from_message_content(
                list(message_event.llm_message.content), has_exactly_one=False
            )
            if text:
                return text

        return None

    def _to_message_event(self, event_data: dict[str, Any]) -> MessageEvent | None:
        """Convert raw event data to a MessageEvent."""
        try:
            return MessageEvent(**event_data)
        except Exception:
            return None

    def _load_event_from_file(self, event_file: Path) -> Event | None:
        """Load and validate an event from a file."""
        try:
            with open(event_file, encoding="utf-8") as f:
                event_data = json.load(f)
            return self._event_adapter.validate_python(event_data)
        except (OSError, json.JSONDecodeError, ValueError):
            return None
