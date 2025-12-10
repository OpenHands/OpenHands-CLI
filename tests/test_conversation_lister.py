import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from openhands_cli.conversations.lister import ConversationInfo, ConversationLister


class TestConversationLister:
    """Test cases for ConversationLister."""
    
    def test_empty_directory(self):
        """Test listing conversations from empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('openhands_cli.conversations.lister.CONVERSATIONS_DIR', temp_dir):
                lister = ConversationLister()
                conversations = lister.list()
                assert conversations == []
    
    def test_nonexistent_directory(self):
        """Test listing conversations from nonexistent directory."""
        with patch('openhands_cli.conversations.lister.CONVERSATIONS_DIR', "/nonexistent/path"):
            lister = ConversationLister()
            conversations = lister.list()
            assert conversations == []
    
    def test_single_conversation(self):
        """Test listing a single valid conversation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('openhands_cli.conversations.lister.CONVERSATIONS_DIR', temp_dir):
                # Create conversation directory structure
                conv_id = "018e3597b3c242a8b930b2aada0bcdbd"
                conv_dir = Path(temp_dir) / conv_id
                events_dir = conv_dir / "events"
                events_dir.mkdir(parents=True)
                
                # Create first event (SystemPromptEvent)
                first_event = {
                    "kind": "SystemPromptEvent",
                    "id": "657fde4a-8d61-487f-a473-3f6808bf1231",
                    "timestamp": "2025-10-21T15:17:29.421124",
                    "source": "agent",
                    "system_prompt": {
                        "cache_prompt": False,
                        "type": "text",
                        "text": "You are OpenHands agent..."
                    }
                }
                
                with open(events_dir / "event-00000-657fde4a-8d61-487f-a473-3f6808bf1231.json", 'w') as f:
                    json.dump(first_event, f)
                
                # Create user message event
                user_event = {
                    "kind": "MessageEvent",
                    "id": "user-message-id",
                    "timestamp": "2025-10-21T15:18:00.000000",
                    "source": "user",
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": "Hello, please help me with my code"
                            }
                        ]
                    }
                }
                
                with open(events_dir / "event-00001-user-message-id.json", 'w') as f:
                    json.dump(user_event, f)
                
                # Test listing
                lister = ConversationLister()
                conversations = lister.list()
                
                assert len(conversations) == 1
                conv = conversations[0]
                assert conv.id == conv_id
                assert conv.first_user_prompt == "Hello, please help me with my code"
                assert conv.created_date == datetime.fromisoformat("2025-10-21T15:17:29.421124")
    
    def test_multiple_conversations_sorted_by_date(self):
        """Test listing multiple conversations sorted by creation date."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('openhands_cli.conversations.lister.CONVERSATIONS_DIR', temp_dir):
                # Create first conversation (older)
                conv1_id = "conv1"
                conv1_dir = Path(temp_dir) / conv1_id
                events1_dir = conv1_dir / "events"
                events1_dir.mkdir(parents=True)
                
                first_event1 = {
                    "kind": "SystemPromptEvent",
                    "id": "event1",
                    "timestamp": "2025-10-20T10:00:00.000000",
                    "source": "agent"
                }
                
                user_event1 = {
                    "kind": "MessageEvent",
                    "id": "user1",
                    "timestamp": "2025-10-20T10:01:00.000000",
                    "source": "user",
                    "message": {
                        "content": [{"type": "text", "text": "First conversation"}]
                    }
                }
                
                with open(events1_dir / "event-00000-event1.json", 'w') as f:
                    json.dump(first_event1, f)
                with open(events1_dir / "event-00001-user1.json", 'w') as f:
                    json.dump(user_event1, f)
                
                # Create second conversation (newer)
                conv2_id = "conv2"
                conv2_dir = Path(temp_dir) / conv2_id
                events2_dir = conv2_dir / "events"
                events2_dir.mkdir(parents=True)
                
                first_event2 = {
                    "kind": "SystemPromptEvent",
                    "id": "event2",
                    "timestamp": "2025-10-21T10:00:00.000000",
                    "source": "agent"
                }
                
                user_event2 = {
                    "kind": "MessageEvent",
                    "id": "user2",
                    "timestamp": "2025-10-21T10:01:00.000000",
                    "source": "user",
                    "message": {
                        "content": [{"type": "text", "text": "Second conversation"}]
                    }
                }
                
                with open(events2_dir / "event-00000-event2.json", 'w') as f:
                    json.dump(first_event2, f)
                with open(events2_dir / "event-00001-user2.json", 'w') as f:
                    json.dump(user_event2, f)
                
                # Test listing
                lister = ConversationLister()
                conversations = lister.list()
                
                assert len(conversations) == 2
                # Should be sorted by date, newest first
                assert conversations[0].id == conv2_id
                assert conversations[0].first_user_prompt == "Second conversation"
                assert conversations[1].id == conv1_id
                assert conversations[1].first_user_prompt == "First conversation"
    
    def test_conversation_without_user_message(self):
        """Test conversation that has no user messages."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('openhands_cli.conversations.lister.CONVERSATIONS_DIR', temp_dir):
                conv_id = "no_user_msg"
                conv_dir = Path(temp_dir) / conv_id
                events_dir = conv_dir / "events"
                events_dir.mkdir(parents=True)
                
                # Only system event, no user message
                system_event = {
                    "kind": "SystemPromptEvent",
                    "id": "system-id",
                    "timestamp": "2025-10-21T15:17:29.421124",
                    "source": "agent"
                }
                
                with open(events_dir / "event-00000-system-id.json", 'w') as f:
                    json.dump(system_event, f)
                
                lister = ConversationLister()
                conversations = lister.list()
                
                assert len(conversations) == 1
                conv = conversations[0]
                assert conv.id == conv_id
                assert conv.first_user_prompt is None
    
    def test_invalid_conversation_directory(self):
        """Test handling of invalid conversation directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('openhands_cli.conversations.lister.CONVERSATIONS_DIR', temp_dir):
                # Create directory without events subdirectory
                invalid_dir = Path(temp_dir) / "invalid_conv"
                invalid_dir.mkdir()
                
                # Create directory with empty events subdirectory
                empty_conv_dir = Path(temp_dir) / "empty_conv"
                empty_events_dir = empty_conv_dir / "events"
                empty_events_dir.mkdir(parents=True)
                
                # Create directory with invalid JSON
                invalid_json_dir = Path(temp_dir) / "invalid_json"
                invalid_json_events_dir = invalid_json_dir / "events"
                invalid_json_events_dir.mkdir(parents=True)
                
                with open(invalid_json_events_dir / "event-00000-invalid.json", 'w') as f:
                    f.write("invalid json content")
                
                lister = ConversationLister()
                conversations = lister.list()
                
                # Should skip all invalid directories
                assert conversations == []