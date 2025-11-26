"""Tests for conversation history management."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from openhands_cli.conversation_history import (
    ConversationInfo,
    get_all_user_messages,
    get_conversation_created_time,
    get_conversation_initial_message,
    get_total_conversation_count,
    is_valid_uuid_hex,
    list_conversations,
)


@pytest.fixture
def temp_conversations_dir(monkeypatch):
    """Create a temporary conversations directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Monkeypatch the CONVERSATIONS_DIR
        monkeypatch.setattr("openhands_cli.conversation_history.CONVERSATIONS_DIR", tmpdir)
        yield Path(tmpdir)


def create_test_conversation(
    conversations_dir: Path,
    conversation_id: UUID | None = None,
    messages: list[str] | None = None,
) -> UUID:
    """Create a test conversation with the given messages.

    Args:
        conversations_dir: Path to conversations directory
        conversation_id: Optional UUID for the conversation
        messages: List of user messages to create

    Returns:
        UUID of the created conversation
    """
    if conversation_id is None:
        conversation_id = uuid4()

    if messages is None:
        messages = ["Hello, agent!"]

    # Create conversation directory
    conv_dir = conversations_dir / conversation_id.hex
    conv_dir.mkdir(parents=True, exist_ok=True)

    # Create event files with user messages
    for i, message in enumerate(messages):
        event_file = conv_dir / f"{i}.json"
        event_data = {
            "action": "message",
            "source": "user",
            "args": {
                "content": [{"type": "text", "text": message}]
            },
        }
        with open(event_file, "w") as f:
            json.dump(event_data, f)

    return conversation_id


class TestIsValidUuidHex:
    """Tests for is_valid_uuid_hex function."""

    def test_valid_uuid_hex(self):
        """Test with a valid UUID hex string."""
        uuid_obj = uuid4()
        assert is_valid_uuid_hex(uuid_obj.hex) is True

    def test_invalid_uuid_hex(self):
        """Test with an invalid UUID hex string."""
        assert is_valid_uuid_hex("not-a-uuid") is False
        assert is_valid_uuid_hex("12345") is False

    def test_empty_string(self):
        """Test with an empty string."""
        assert is_valid_uuid_hex("") is False


class TestGetConversationInitialMessage:
    """Tests for get_conversation_initial_message function."""

    def test_get_initial_message(self, temp_conversations_dir):
        """Test getting initial message from a conversation."""
        conv_id = create_test_conversation(
            temp_conversations_dir,
            messages=["First message", "Second message"]
        )
        conv_dir = temp_conversations_dir / conv_id.hex

        message = get_conversation_initial_message(conv_dir)
        assert message == "First message"

    def test_no_messages(self, temp_conversations_dir):
        """Test with a conversation that has no user messages."""
        conv_id = uuid4()
        conv_dir = temp_conversations_dir / conv_id.hex
        conv_dir.mkdir(parents=True, exist_ok=True)

        message = get_conversation_initial_message(conv_dir)
        assert message is None

    def test_non_existent_directory(self, temp_conversations_dir):
        """Test with a non-existent directory."""
        conv_dir = temp_conversations_dir / "nonexistent"

        message = get_conversation_initial_message(conv_dir)
        assert message is None

    def test_message_with_string_content(self, temp_conversations_dir):
        """Test with message content as a string (legacy format)."""
        conv_id = uuid4()
        conv_dir = temp_conversations_dir / conv_id.hex
        conv_dir.mkdir(parents=True, exist_ok=True)

        # Create event with string content
        event_file = conv_dir / "0.json"
        event_data = {
            "action": "message",
            "source": "user",
            "args": {
                "content": "String content message"
            },
        }
        with open(event_file, "w") as f:
            json.dump(event_data, f)

        message = get_conversation_initial_message(conv_dir)
        assert message == "String content message"


class TestGetConversationCreatedTime:
    """Tests for get_conversation_created_time function."""

    def test_get_created_time(self, temp_conversations_dir):
        """Test getting creation time from a conversation."""
        conv_id = create_test_conversation(temp_conversations_dir)
        conv_dir = temp_conversations_dir / conv_id.hex

        created_time = get_conversation_created_time(conv_dir)
        assert isinstance(created_time, datetime)
        assert created_time.year >= 2024


class TestListConversations:
    """Tests for list_conversations function."""

    def test_list_empty_directory(self, temp_conversations_dir):
        """Test listing conversations from an empty directory."""
        conversations = list_conversations()
        assert conversations == []

    def test_list_conversations(self, temp_conversations_dir):
        """Test listing multiple conversations."""
        # Create multiple conversations
        conv_id1 = create_test_conversation(
            temp_conversations_dir,
            messages=["First conversation"]
        )
        conv_id2 = create_test_conversation(
            temp_conversations_dir,
            messages=["Second conversation"]
        )

        conversations = list_conversations()
        assert len(conversations) == 2

        # Check that conversations are returned
        conv_ids = {conv.id for conv in conversations}
        assert conv_id1 in conv_ids
        assert conv_id2 in conv_ids

    def test_list_conversations_with_limit(self, temp_conversations_dir):
        """Test listing conversations with a limit."""
        # Create 5 conversations
        for i in range(5):
            create_test_conversation(
                temp_conversations_dir,
                messages=[f"Message {i}"]
            )

        conversations = list_conversations(limit=3)
        assert len(conversations) == 3

    def test_list_conversations_with_offset(self, temp_conversations_dir):
        """Test listing conversations with offset for pagination."""
        # Create 5 conversations
        for i in range(5):
            create_test_conversation(
                temp_conversations_dir,
                messages=[f"Message {i}"]
            )

        # Get first page
        page1 = list_conversations(limit=2, offset=0)
        assert len(page1) == 2

        # Get second page
        page2 = list_conversations(limit=2, offset=2)
        assert len(page2) == 2

        # Ensure different conversations
        page1_ids = {conv.id for conv in page1}
        page2_ids = {conv.id for conv in page2}
        assert page1_ids.isdisjoint(page2_ids)


class TestGetAllUserMessages:
    """Tests for get_all_user_messages function."""

    def test_get_all_messages(self, temp_conversations_dir):
        """Test getting all user messages from a conversation."""
        messages = ["First message", "Second message", "Third message"]
        conv_id = create_test_conversation(temp_conversations_dir, messages=messages)

        retrieved_messages = get_all_user_messages(conv_id)
        assert retrieved_messages == messages

    def test_get_messages_non_existent(self, temp_conversations_dir):
        """Test getting messages from non-existent conversation."""
        conv_id = uuid4()
        messages = get_all_user_messages(conv_id)
        assert messages == []

    def test_get_messages_mixed_events(self, temp_conversations_dir):
        """Test getting messages when there are mixed event types."""
        conv_id = uuid4()
        conv_dir = temp_conversations_dir / conv_id.hex
        conv_dir.mkdir(parents=True, exist_ok=True)

        # Create mix of user messages and other events
        events = [
            {
                "action": "message",
                "source": "user",
                "args": {"content": [{"type": "text", "text": "User message 1"}]},
            },
            {
                "action": "message",
                "source": "agent",
                "args": {"content": [{"type": "text", "text": "Agent response"}]},
            },
            {
                "action": "message",
                "source": "user",
                "args": {"content": [{"type": "text", "text": "User message 2"}]},
            },
        ]

        for i, event_data in enumerate(events):
            event_file = conv_dir / f"{i}.json"
            with open(event_file, "w") as f:
                json.dump(event_data, f)

        messages = get_all_user_messages(conv_id)
        assert len(messages) == 2
        assert messages == ["User message 1", "User message 2"]


class TestGetTotalConversationCount:
    """Tests for get_total_conversation_count function."""

    def test_count_empty(self, temp_conversations_dir):
        """Test count with no conversations."""
        count = get_total_conversation_count()
        assert count == 0

    def test_count_multiple(self, temp_conversations_dir):
        """Test count with multiple conversations."""
        for i in range(7):
            create_test_conversation(
                temp_conversations_dir,
                messages=[f"Message {i}"]
            )

        count = get_total_conversation_count()
        assert count == 7


class TestConversationInfo:
    """Tests for ConversationInfo dataclass."""

    def test_string_representation(self):
        """Test the string representation of ConversationInfo."""
        conv_id = uuid4()
        created_at = datetime(2024, 1, 15, 10, 30, 45)
        initial_message = "Hello, this is a test message"

        conv_info = ConversationInfo(
            id=conv_id,
            created_at=created_at,
            initial_message=initial_message,
        )

        result = str(conv_info)
        assert str(conv_id) in result
        assert "2024-01-15 10:30:45" in result
        assert initial_message in result

    def test_string_representation_truncated(self):
        """Test truncation of long messages."""
        conv_id = uuid4()
        created_at = datetime(2024, 1, 15, 10, 30, 45)
        initial_message = "a" * 150  # 150 character message

        conv_info = ConversationInfo(
            id=conv_id,
            created_at=created_at,
            initial_message=initial_message,
        )

        result = str(conv_info)
        # Should be truncated to 100 chars + "..."
        assert len(initial_message) > 100
        assert "..." in result
        # The displayed message should not exceed 103 characters (100 + "...")
        assert "a" * 100 + "..." in result
