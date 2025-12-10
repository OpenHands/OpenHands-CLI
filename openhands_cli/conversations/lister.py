from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from openhands.sdk import MessageEvent
from openhands.sdk.llm.message import TextContent
from openhands_cli.locations import CONVERSATIONS_DIR


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
            try:
                with open(event_file, encoding="utf-8") as f:
                    event_data = json.load(f)

                # Try to convert JSON to MessageEvent
                try:
                    message_event = MessageEvent(**event_data)
                except Exception:
                    # Try to transform old format to new format
                    try:
                        transformed_data = self._transform_old_message_format(
                            event_data
                        )
                        message_event = MessageEvent(**transformed_data)
                    except Exception:
                        # If it doesn't convert, skip this event
                        continue

                # Check if this is a user message event
                if message_event.source == "user":
                    # Access the typed object attributes
                    for content_item in message_event.llm_message.content:
                        if isinstance(content_item, TextContent):
                            text = content_item.text.strip()
                            if text:
                                return text

            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        return None

    def _transform_old_message_format(self, event_data: dict) -> dict:
        """Transform old message format to new MessageEvent format.

        Args:
            event_data: Event data in old format.

        Returns:
            Event data in new format.
        """
        if (
            event_data.get("kind") == "MessageEvent"
            and "message" in event_data
            and "llm_message" not in event_data
        ):
            transformed = event_data.copy()
            # Move message to llm_message and add role
            transformed["llm_message"] = event_data["message"].copy()
            transformed["llm_message"]["role"] = event_data["source"]
            del transformed["message"]
            return transformed

        return event_data

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
