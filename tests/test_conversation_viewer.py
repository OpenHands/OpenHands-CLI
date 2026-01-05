"""Tests for the conversation viewer functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from openhands_cli.conversations.viewer import ConversationViewer, view_conversation


class TestConversationViewer:
    """Test cases for ConversationViewer."""

    def _create_conversation_with_events(
        self, temp_dir: str, conv_id: str, events: list[dict]
    ) -> Path:
        """Helper to create a conversation directory with events.

        Args:
            temp_dir: The temporary directory to create the conversation in.
            conv_id: The conversation ID.
            events: List of event dictionaries to create.

        Returns:
            Path to the conversation directory.
        """
        conv_dir = Path(temp_dir) / conv_id
        events_dir = conv_dir / "events"
        events_dir.mkdir(parents=True)

        for i, event in enumerate(events):
            event_file = events_dir / f"event-{i:05d}.json"
            with open(event_file, "w") as f:
                json.dump(event, f)

        return conv_dir

    def test_view_nonexistent_conversation(self):
        """Test viewing a conversation that doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.viewer.CONVERSATIONS_DIR", temp_dir
            ):
                viewer = ConversationViewer()
                result = viewer.view("nonexistent-conversation-id")
                assert result is False

    def test_view_conversation_without_events_dir(self):
        """Test viewing a conversation without an events directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.viewer.CONVERSATIONS_DIR", temp_dir
            ):
                # Create conversation directory without events subdirectory
                conv_dir = Path(temp_dir) / "test-conv"
                conv_dir.mkdir()

                viewer = ConversationViewer()
                result = viewer.view("test-conv")
                assert result is False

    def test_view_conversation_with_empty_events_dir(self):
        """Test viewing a conversation with an empty events directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.viewer.CONVERSATIONS_DIR", temp_dir
            ):
                # Create conversation directory with empty events subdirectory
                conv_dir = Path(temp_dir) / "test-conv"
                events_dir = conv_dir / "events"
                events_dir.mkdir(parents=True)

                viewer = ConversationViewer()
                result = viewer.view("test-conv")
                assert result is False

    def test_view_single_event(self):
        """Test viewing a conversation with a single event."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.viewer.CONVERSATIONS_DIR", temp_dir
            ):
                events = [
                    {
                        "kind": "MessageEvent",
                        "id": "test-event-id",
                        "timestamp": "2025-01-01T00:00:00",
                        "source": "user",
                        "llm_message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Hello, world!"}],
                        },
                    }
                ]

                self._create_conversation_with_events(temp_dir, "test-conv", events)

                viewer = ConversationViewer()
                result = viewer.view("test-conv")
                assert result is True

    def test_view_multiple_events(self):
        """Test viewing a conversation with multiple events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.viewer.CONVERSATIONS_DIR", temp_dir
            ):
                events = [
                    {
                        "kind": "MessageEvent",
                        "id": "event-1",
                        "timestamp": "2025-01-01T00:00:00",
                        "source": "user",
                        "llm_message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Hello!"}],
                        },
                    },
                    {
                        "kind": "MessageEvent",
                        "id": "event-2",
                        "timestamp": "2025-01-01T00:00:01",
                        "source": "agent",
                        "llm_message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "Hi there!"}],
                        },
                    },
                    {
                        "kind": "MessageEvent",
                        "id": "event-3",
                        "timestamp": "2025-01-01T00:00:02",
                        "source": "user",
                        "llm_message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "How are you?"}],
                        },
                    },
                ]

                self._create_conversation_with_events(temp_dir, "test-conv", events)

                viewer = ConversationViewer()
                result = viewer.view("test-conv")
                assert result is True

    def test_view_with_limit(self):
        """Test viewing a conversation with a limit on events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.viewer.CONVERSATIONS_DIR", temp_dir
            ):
                # Create 5 events
                events = [
                    {
                        "kind": "MessageEvent",
                        "id": f"event-{i}",
                        "timestamp": f"2025-01-01T00:00:0{i}",
                        "source": "user",
                        "llm_message": {
                            "role": "user",
                            "content": [{"type": "text", "text": f"Message {i}"}],
                        },
                    }
                    for i in range(5)
                ]

                self._create_conversation_with_events(temp_dir, "test-conv", events)

                viewer = ConversationViewer()
                # View with limit of 2
                result = viewer.view("test-conv", limit=2)
                assert result is True

    def test_view_with_invalid_json(self):
        """Test viewing a conversation with an invalid JSON event file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.viewer.CONVERSATIONS_DIR", temp_dir
            ):
                conv_dir = Path(temp_dir) / "test-conv"
                events_dir = conv_dir / "events"
                events_dir.mkdir(parents=True)

                # Create an invalid JSON file
                invalid_file = events_dir / "event-00000.json"
                with open(invalid_file, "w") as f:
                    f.write("invalid json content")

                # Create a valid event file
                valid_event = {
                    "kind": "MessageEvent",
                    "id": "valid-event",
                    "timestamp": "2025-01-01T00:00:00",
                    "source": "user",
                    "llm_message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "Valid message"}],
                    },
                }
                valid_file = events_dir / "event-00001.json"
                with open(valid_file, "w") as f:
                    json.dump(valid_event, f)

                viewer = ConversationViewer()
                # Should still succeed because there's at least one valid event
                result = viewer.view("test-conv")
                assert result is True


class TestViewConversationFunction:
    """Test cases for the view_conversation helper function."""

    def test_view_conversation_function(self):
        """Test the view_conversation helper function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.viewer.CONVERSATIONS_DIR", temp_dir
            ):
                # Create a conversation
                conv_dir = Path(temp_dir) / "test-conv"
                events_dir = conv_dir / "events"
                events_dir.mkdir(parents=True)

                event = {
                    "kind": "MessageEvent",
                    "id": "test-event",
                    "timestamp": "2025-01-01T00:00:00",
                    "source": "user",
                    "llm_message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "Test message"}],
                    },
                }
                event_file = events_dir / "event-00000.json"
                with open(event_file, "w") as f:
                    json.dump(event, f)

                result = view_conversation("test-conv", limit=10)
                assert result is True

    def test_view_conversation_function_not_found(self):
        """Test the view_conversation helper function with nonexistent conversation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.viewer.CONVERSATIONS_DIR", temp_dir
            ):
                result = view_conversation("nonexistent-conv")
                assert result is False
