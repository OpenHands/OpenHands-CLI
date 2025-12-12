from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from openhands.sdk import MessageEvent
from openhands_cli.locations import CONVERSATIONS_DIR
from openhands_cli.utils import extract_text_from_message_content


class ConversationInfo(BaseModel):
    """Information about a conversation."""

    id: str
    first_user_prompt: str | None
    created_date: datetime


class ConversationLister:
    """Class for listing and managing conversations."""

    def __init__(self):
        """Initialize the conversation lister."""
        self.conversations_dir = CONVERSATIONS_DIR

    def list(self) -> list[ConversationInfo]:
        """List all conversations with their first user prompts and creation dates.

        Returns:
            List of ConversationInfo objects sorted by latest conversations first.
        """
        conversations = []
        conversations_path = Path(self.conversations_dir)

        if not conversations_path.exists():
            return conversations

        # Iterate through all conversation directories
        for conversation_dir in conversations_path.iterdir():
            if not conversation_dir.is_dir():
                continue

            conversation_info = self._parse_conversation(conversation_dir)
            if conversation_info:
                conversations.append(conversation_info)

        # Sort by creation date, latest first
        conversations.sort(key=lambda x: x.created_date, reverse=True)
        return conversations

    def _parse_conversation(self, conversation_dir: Path) -> ConversationInfo | None:
        """Parse a single conversation directory.

        Args:
            conversation_dir: Path to the conversation directory.

        Returns:
            ConversationInfo if valid conversation, None otherwise.
        """
        events_dir = conversation_dir / "events"

        # Check if events directory exists
        if not events_dir.exists() or not events_dir.is_dir():
            return None

        # Get all event files and sort them
        event_files = list(events_dir.glob("event-*.json"))
        if not event_files:
            return None

        # Sort event files by name to get the first one
        event_files.sort()
        first_event_file = event_files[0]

        try:
            # Parse the first event file
            with open(first_event_file, encoding="utf-8") as f:
                first_event = json.load(f)

            # Extract timestamp from the first event
            timestamp_str = first_event.get("timestamp")
            if not timestamp_str:
                return None

            # Parse the timestamp
            created_date = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            # Find the first user message event
            first_user_prompt = self._find_first_user_prompt(event_files)

            return ConversationInfo(
                id=conversation_dir.name,
                first_user_prompt=first_user_prompt,
                created_date=created_date,
            )

        except (json.JSONDecodeError, ValueError, KeyError):
            # Skip invalid conversation directories
            return None

    def _find_first_user_prompt(self, event_files: list[Path]) -> str | None:
        """Find the first user prompt in the conversation events.

        Args:
            event_files: List of event file paths sorted by name.

        Returns:
            First user prompt text or None if not found.
        """
        for event_file in event_files:
            event_data = self._load_event_data(event_file)
            if event_data is None:
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

    def _load_event_data(self, event_file: Path) -> dict[str, Any] | None:
        """Safely load JSON event data from a file."""
        try:
            with open(event_file, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def _to_message_event(self, event_data: dict[str, Any]) -> MessageEvent | None:
        """Convert raw event data to a MessageEvent."""
        try:
            return MessageEvent(**event_data)
        except Exception:
            return None

    def get_latest_conversation_id(self) -> str | None:
        """Get the ID of the most recent conversation.

        Returns:
            The conversation ID of the most recent conversation, or None if no
            conversations exist.
        """
        conversations = self.list()
        if not conversations:
            return None

        # Conversations are already sorted by created_date (latest first)
        return conversations[0].id
