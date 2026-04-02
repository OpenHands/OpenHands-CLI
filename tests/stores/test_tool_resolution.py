"""Tests for tool resolution with backward compatibility for DelegateTool."""

import json

import pytest

from openhands.sdk.tool import Tool
from openhands_cli.stores.agent_store import AgentStore


class TestResolveToolsBackwardCompatibility:
    """Tests for _resolve_tools method backward compatibility with DelegateTool."""

    @pytest.fixture
    def agent_store(self, tmp_path, monkeypatch):
        """Create an AgentStore with a temporary directory."""
        monkeypatch.setattr(
            "openhands_cli.stores.agent_store.get_persistence_dir",
            lambda: str(tmp_path / "persistence"),
        )
        monkeypatch.setattr(
            "openhands_cli.stores.agent_store.get_conversations_dir",
            lambda: str(tmp_path / "conversations"),
        )
        # Also patch in utils.py since conversation_has_delegate_tool_events uses it
        monkeypatch.setattr(
            "openhands_cli.utils.get_conversations_dir",
            lambda: str(tmp_path / "conversations"),
        )
        return AgentStore()

    def test_new_conversation_uses_task_tool_set(self, agent_store):
        """Test that new conversations (no session_id) use TaskToolSet."""
        tools = agent_store._resolve_tools(None)
        tool_names = {t.name for t in tools}
        assert "task_tool_set" in tool_names
        assert "delegate" not in tool_names

    def test_conversation_with_delegate_events_uses_delegate_tool(
        self, agent_store, tmp_path
    ):
        """Test conversations with DelegateTool events continue using DelegateTool."""
        conv_id = "legacy-conversation-123"
        events_dir = tmp_path / "conversations" / conv_id / "events"
        events_dir.mkdir(parents=True)

        # Create event files with a delegate event
        events = [
            {"tool_name": "terminal", "id": "event-1"},
            {"tool_name": "delegate", "id": "event-2"},  # Legacy DelegateTool usage
        ]
        for i, event in enumerate(events):
            event_file = events_dir / f"event-{i:05d}-abc123.json"
            event_file.write_text(json.dumps(event))

        tools = agent_store._resolve_tools(conv_id)
        tool_names = {t.name for t in tools}
        assert "delegate" in tool_names
        assert "task_tool_set" not in tool_names

    def test_conversation_without_delegate_events_uses_task_tool_set(
        self, agent_store, tmp_path
    ):
        """Test that conversations without DelegateTool events use TaskToolSet."""
        conv_id = "new-conversation-456"
        events_dir = tmp_path / "conversations" / conv_id / "events"
        events_dir.mkdir(parents=True)

        # Create event files without any delegate events
        events = [
            {"tool_name": "terminal", "id": "event-1"},
            {"tool_name": "file_editor", "id": "event-2"},
        ]
        for i, event in enumerate(events):
            event_file = events_dir / f"event-{i:05d}-abc123.json"
            event_file.write_text(json.dumps(event))

        tools = agent_store._resolve_tools(conv_id)
        tool_names = {t.name for t in tools}
        assert "task_tool_set" in tool_names
        assert "delegate" not in tool_names

    def test_persisted_tools_take_precedence(self, agent_store, tmp_path, monkeypatch):
        """Test that tools from base_state.json take precedence over detection."""
        conv_id = "persisted-conversation-789"
        events_dir = tmp_path / "conversations" / conv_id / "events"
        events_dir.mkdir(parents=True)

        # Create delegate event (would normally trigger DelegateTool)
        event_file = events_dir / "event-00000-abc.json"
        event_file.write_text(json.dumps({"tool_name": "delegate"}))

        # Mock get_persisted_conversation_tools to return custom tools
        custom_tools = [
            Tool(name="custom_tool_1"),
            Tool(name="custom_tool_2"),
        ]
        monkeypatch.setattr(
            "openhands_cli.stores.agent_store.get_persisted_conversation_tools",
            lambda _: custom_tools,
        )

        tools = agent_store._resolve_tools(conv_id)
        tool_names = {t.name for t in tools}

        # Should use persisted tools, not detect from events
        assert tool_names == {"custom_tool_1", "custom_tool_2"}
        assert "delegate" not in tool_names
        assert "task_tool_set" not in tool_names

    def test_nonexistent_conversation_uses_task_tool_set(self, agent_store):
        """Test that nonexistent conversations fall back to TaskToolSet."""
        tools = agent_store._resolve_tools("nonexistent-conversation")
        tool_names = {t.name for t in tools}
        assert "task_tool_set" in tool_names
        assert "delegate" not in tool_names
