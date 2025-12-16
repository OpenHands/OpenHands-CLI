import json
import tempfile
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openhands_cli.conversations.lister import ConversationLister
from openhands_cli.simple_main import handle_resume_logic


class TestConversationLister:
    """Test cases for ConversationLister."""

    @pytest.mark.parametrize(
        "directory_type,expected_result",
        [
            ("empty", []),
            ("nonexistent", []),
        ],
    )
    def test_empty_or_nonexistent_directory(self, directory_type, expected_result):
        """Test listing conversations from empty or nonexistent directories."""
        if directory_type == "empty":
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch(
                    "openhands_cli.conversations.lister.CONVERSATIONS_DIR", temp_dir
                ):
                    lister = ConversationLister()
                    conversations = lister.list()
                    assert conversations == expected_result
        else:  # nonexistent
            with patch(
                "openhands_cli.conversations.lister.CONVERSATIONS_DIR",
                "/nonexistent/path",
            ):
                lister = ConversationLister()
                conversations = lister.list()
                assert conversations == expected_result

    def _create_conversation_with_events(
        self, temp_dir, conv_id, timestamp, user_message=None
    ):
        """Helper to create a conversation directory with events."""
        conv_dir = Path(temp_dir) / conv_id
        events_dir = conv_dir / "events"
        events_dir.mkdir(parents=True)

        # Create first event (SystemPromptEvent)
        first_event = {
            "kind": "SystemPromptEvent",
            "id": "system-event-id",
            "timestamp": timestamp,
            "source": "agent",
        }

        with open(events_dir / "event-00000-system.json", "w") as f:
            json.dump(first_event, f)

        # Create user message event if provided
        if user_message:
            user_event = {
                "kind": "MessageEvent",
                "id": "user-message-id",
                "timestamp": timestamp,
                "source": "user",
                "llm_message": {
                    "role": "user",
                    "content": [{"type": "text", "text": user_message}],
                },
            }

            with open(events_dir / "event-00001-user.json", "w") as f:
                json.dump(user_event, f)

        return conv_dir

    def test_single_conversation(self):
        """Test listing a single valid conversation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.lister.CONVERSATIONS_DIR", temp_dir
            ):
                conv_id = "test-conversation-id"
                timestamp = "2025-10-21T15:17:29.421124"
                user_message = "Hello, please help me with my code"

                self._create_conversation_with_events(
                    temp_dir, conv_id, timestamp, user_message
                )

                # Test listing
                lister = ConversationLister()
                conversations = lister.list()

                assert len(conversations) == 1
                conv = conversations[0]
                assert conv.id == conv_id
                assert conv.first_user_prompt == user_message
                assert conv.created_date == datetime.fromisoformat(timestamp)

    def test_multiple_conversations_sorted_by_date(self):
        """Test listing multiple conversations sorted by creation date."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.lister.CONVERSATIONS_DIR", temp_dir
            ):
                # Create conversations with different timestamps
                conversations_data = [
                    ("conv1", "2025-10-20T10:00:00.000000", "First conversation"),
                    ("conv2", "2025-10-21T10:00:00.000000", "Second conversation"),
                ]

                for conv_id, timestamp, user_message in conversations_data:
                    self._create_conversation_with_events(
                        temp_dir, conv_id, timestamp, user_message
                    )

                # Test listing
                lister = ConversationLister()
                conversations = lister.list()

                assert len(conversations) == 2
                # Should be sorted by date, newest first
                assert conversations[0].id == "conv2"
                assert conversations[0].first_user_prompt == "Second conversation"
                assert conversations[1].id == "conv1"
                assert conversations[1].first_user_prompt == "First conversation"

    def test_conversation_without_user_message(self):
        """Test conversation that has no user messages."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.lister.CONVERSATIONS_DIR", temp_dir
            ):
                conv_id = "no_user_msg"
                timestamp = "2025-10-21T15:17:29.421124"

                # Create conversation without user message
                self._create_conversation_with_events(temp_dir, conv_id, timestamp)

                lister = ConversationLister()
                conversations = lister.list()

                assert len(conversations) == 1
                conv = conversations[0]
                assert conv.id == conv_id
                assert conv.first_user_prompt is None

    @pytest.mark.parametrize(
        "invalid_type",
        ["no_events_dir", "empty_events_dir", "invalid_json"],
    )
    def test_invalid_conversation_directories(self, invalid_type):
        """Test handling of various invalid conversation directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "openhands_cli.conversations.lister.CONVERSATIONS_DIR", temp_dir
            ):
                conv_dir = Path(temp_dir) / "invalid_conv"

                if invalid_type == "no_events_dir":
                    # Directory without events subdirectory
                    conv_dir.mkdir()
                elif invalid_type == "empty_events_dir":
                    # Directory with empty events subdirectory
                    events_dir = conv_dir / "events"
                    events_dir.mkdir(parents=True)
                elif invalid_type == "invalid_json":
                    # Directory with invalid JSON
                    events_dir = conv_dir / "events"
                    events_dir.mkdir(parents=True)
                    with open(events_dir / "event-00000-invalid.json", "w") as f:
                        f.write("invalid json content")

                lister = ConversationLister()
                conversations = lister.list()

                # Should skip all invalid directories
                assert conversations == []


class TestResumeLogicHandling:
    """Test cases for handle_resume_logic function."""

    @pytest.mark.parametrize(
        "args_dict,expected_result,should_show_output",
        [
            # Test case 1: --resume with no ID (should show conversation list)
            ({"resume": "", "last": False}, None, True),
            # Test case 2: --resume with an ID (should return the ID)
            (
                {"resume": "test-conversation-id", "last": False},
                "test-conversation-id",
                False,
            ),
            # Test case 3: --resume --last (should get latest conversation)
            ({"resume": "", "last": True}, "latest-conv-id", True),
            # Test case 4: just --last flag without --resume (should show error)
            ({"resume": None, "last": True}, None, True),
        ],
    )
    @patch("openhands_cli.simple_main.console.print")
    def test_handle_resume_logic_scenarios(
        self, mock_print, args_dict, expected_result, should_show_output
    ):
        """Test handle_resume_logic with various argument combinations."""
        args = Namespace(**args_dict)

        # Mock conversation lister for --last tests
        with patch(
            "openhands_cli.conversations.lister.ConversationLister"
        ) as mock_lister_cls:
            mock_lister = MagicMock()
            mock_lister_cls.return_value = mock_lister

            if args_dict.get("last") and args_dict.get("resume") is not None:
                # For --resume --last, mock getting latest conversation
                mock_lister.get_latest_conversation_id.return_value = "latest-conv-id"
            else:
                mock_lister.get_latest_conversation_id.return_value = None

            # Mock display_recent_conversations for --resume without ID
            with patch(
                "openhands_cli.conversations.display.display_recent_conversations"
            ) as mock_display:
                result = handle_resume_logic(args)

                assert result == expected_result

                # Verify appropriate functions were called
                if args_dict.get("resume") == "" and not args_dict.get("last"):
                    # --resume without ID should show conversation list
                    mock_display.assert_called_once()
                elif args_dict.get("last") and args_dict.get("resume") is not None:
                    # --resume --last should get latest conversation
                    mock_lister.get_latest_conversation_id.assert_called_once()

                # Verify output was shown when expected
                if should_show_output:
                    assert mock_print.called or mock_display.called

    def test_handle_resume_logic_no_conversations_for_last(self):
        """Test --resume --last when no conversations exist."""
        args = Namespace(resume="", last=True)

        with patch(
            "openhands_cli.conversations.lister.ConversationLister"
        ) as mock_lister_cls:
            mock_lister = MagicMock()
            mock_lister_cls.return_value = mock_lister
            mock_lister.get_latest_conversation_id.return_value = None

            with patch("openhands_cli.simple_main.console.print") as mock_print:
                result = handle_resume_logic(args)

                assert result is None
                mock_print.assert_called()
                # Verify the error message contains expected text
                call_args = mock_print.call_args[0][0]
                assert "No conversations found to resume" in str(call_args)
