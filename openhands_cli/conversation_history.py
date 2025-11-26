"""Conversation history management for OpenHands CLI."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from openhands_cli.locations import CONVERSATIONS_DIR


@dataclass
class ConversationInfo:
    """Information about a conversation."""

    id: UUID
    created_at: datetime
    initial_message: str

    def __str__(self) -> str:
        """Format conversation info for display."""
        # Truncate initial message to 100 characters
        truncated_msg = (
            self.initial_message[:100] + "..."
            if len(self.initial_message) > 100
            else self.initial_message
        )
        # Format the datetime
        created_str = self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        return f"[{self.id}] [Created at: {created_str}] Initial user message: {truncated_msg}"


def get_conversation_initial_message(conversation_dir: Path) -> str | None:
    """Extract the first user message from a conversation's event files.

    Args:
        conversation_dir: Path to the conversation directory

    Returns:
        The first user message content, or None if not found
    """
    # Check JSON files in order (0.json, 1.json, 2.json, ...)
    event_index = 0
    while True:
        event_file = conversation_dir / f"{event_index}.json"
        if not event_file.exists():
            break

        try:
            with open(event_file) as f:
                event_data = json.load(f)

            # Look for message event from user
            if (
                event_data.get("action") == "message"
                and event_data.get("source") == "user"
            ):
                # Get the content from args
                args = event_data.get("args", {})
                content = args.get("content")
                if content:
                    # Content might be a list of content objects or a string
                    if isinstance(content, list) and len(content) > 0:
                        # Get the first text content
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                return item.get("text", "")
                    elif isinstance(content, str):
                        return content
        except (json.JSONDecodeError, OSError):
            # Skip corrupted or unreadable files
            pass

        event_index += 1

    return None


def get_conversation_created_time(conversation_dir: Path) -> datetime:
    """Get the creation time of a conversation.

    Args:
        conversation_dir: Path to the conversation directory

    Returns:
        The creation time as a datetime object
    """
    # Use the modification time of the directory as creation time
    # or the first event file's creation time
    event_0 = conversation_dir / "0.json"
    if event_0.exists():
        timestamp = event_0.stat().st_mtime
    else:
        timestamp = conversation_dir.stat().st_mtime

    return datetime.fromtimestamp(timestamp)


def list_conversations(limit: int = 10, offset: int = 0) -> list[ConversationInfo]:
    """List recent conversations from the conversations directory.

    Args:
        limit: Maximum number of conversations to return
        offset: Number of conversations to skip (for pagination)

    Returns:
        List of ConversationInfo objects, sorted by creation time (newest first)
    """
    conversations_path = Path(CONVERSATIONS_DIR)

    if not conversations_path.exists():
        return []

    # Get all conversation directories
    conversation_dirs = [
        d for d in conversations_path.iterdir() if d.is_dir() and is_valid_uuid_hex(d.name)
    ]

    # Sort by modification time (newest first)
    conversation_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)

    # Apply pagination
    paginated_dirs = conversation_dirs[offset : offset + limit]

    # Extract conversation info
    conversations = []
    for conv_dir in paginated_dirs:
        try:
            # Convert hex directory name back to UUID
            conv_id = UUID(hex=conv_dir.name)
            created_at = get_conversation_created_time(conv_dir)
            initial_message = get_conversation_initial_message(conv_dir)

            if initial_message:
                conversations.append(
                    ConversationInfo(
                        id=conv_id,
                        created_at=created_at,
                        initial_message=initial_message,
                    )
                )
        except (ValueError, OSError):
            # Skip invalid conversation directories
            continue

    return conversations


def get_all_user_messages(conversation_id: UUID) -> list[str]:
    """Get all user messages from a conversation.

    Args:
        conversation_id: UUID of the conversation

    Returns:
        List of user message contents
    """
    conversations_path = Path(CONVERSATIONS_DIR)
    conversation_dir = conversations_path / conversation_id.hex

    if not conversation_dir.exists():
        return []

    messages = []
    event_index = 0

    while True:
        event_file = conversation_dir / f"{event_index}.json"
        if not event_file.exists():
            break

        try:
            with open(event_file) as f:
                event_data = json.load(f)

            # Look for message events from user
            if (
                event_data.get("action") == "message"
                and event_data.get("source") == "user"
            ):
                args = event_data.get("args", {})
                content = args.get("content")
                if content:
                    if isinstance(content, list) and len(content) > 0:
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text = item.get("text", "")
                                if text:
                                    messages.append(text)
                    elif isinstance(content, str):
                        messages.append(content)
        except (json.JSONDecodeError, OSError):
            pass

        event_index += 1

    return messages


def is_valid_uuid_hex(hex_string: str) -> bool:
    """Check if a string is a valid UUID hex representation.

    Args:
        hex_string: String to check

    Returns:
        True if valid UUID hex, False otherwise
    """
    try:
        UUID(hex=hex_string)
        return True
    except (ValueError, AttributeError):
        return False


def get_total_conversation_count() -> int:
    """Get the total number of conversations.

    Returns:
        Total count of conversation directories
    """
    conversations_path = Path(CONVERSATIONS_DIR)

    if not conversations_path.exists():
        return 0

    return len([d for d in conversations_path.iterdir() if d.is_dir() and is_valid_uuid_hex(d.name)])
