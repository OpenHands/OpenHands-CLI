"""Tests for tool resolution with backward compatibility for DelegateTool."""

import json

import pytest

from openhands.sdk.tool import Tool
from openhands_cli.stores.agent_store import AgentStore


@pytest.fixture
def agent_store(tmp_path, monkeypatch):
    """Create an AgentStore with a temporary directory."""
    monkeypatch.setattr(
        "openhands_cli.stores.agent_store.get_persistence_dir",
        lambda: str(tmp_path / "persistence"),
    )
    monkeypatch.setattr(
        "openhands_cli.stores.agent_store.get_conversations_dir",
        lambda: str(tmp_path / "conversations"),
    )
    monkeypatch.setattr(
        "openhands_cli.utils.get_conversations_dir",
        lambda: str(tmp_path / "conversations"),
    )
    return AgentStore()


@pytest.mark.parametrize(
    "session_id",
    [None, "nonexistent-conversation"],
    ids=["new_conversation", "nonexistent_conversation"],
)
def test_no_events_uses_task_tool_set(agent_store, session_id):
    """Test that conversations without events (new or nonexistent) use TaskToolSet."""
    tools = agent_store._resolve_tools(session_id)
    tool_names = {t.name for t in tools}
    assert "task_tool_set" in tool_names
    assert "delegate" not in tool_names


@pytest.mark.parametrize(
    ("events", "expected_tool", "unexpected_tool"),
    [
        (
            [{"tool_name": "terminal"}, {"tool_name": "delegate"}],
            "delegate",
            "task_tool_set",
        ),
        (
            [{"tool_name": "terminal"}, {"tool_name": "file_editor"}],
            "task_tool_set",
            "delegate",
        ),
    ],
    ids=["with_delegate_events", "without_delegate_events"],
)
def test_event_based_tool_resolution(
    agent_store, tmp_path, events, expected_tool, unexpected_tool
):
    """Test that tool resolution depends on presence of DelegateTool events."""
    conv_id = "test-conversation"
    events_dir = tmp_path / "conversations" / conv_id / "events"
    events_dir.mkdir(parents=True)

    for i, event in enumerate(events):
        event_file = events_dir / f"event-{i:05d}-abc123.json"
        event_file.write_text(json.dumps(event))

    tools = agent_store._resolve_tools(conv_id)
    tool_names = {t.name for t in tools}
    assert expected_tool in tool_names
    assert unexpected_tool not in tool_names


def test_persisted_tools_take_precedence(agent_store, tmp_path, monkeypatch):
    """Test that tools from base_state.json take precedence over detection."""
    conv_id = "persisted-conversation-789"
    events_dir = tmp_path / "conversations" / conv_id / "events"
    events_dir.mkdir(parents=True)

    event_file = events_dir / "event-00000-abc.json"
    event_file.write_text(json.dumps({"tool_name": "delegate"}))

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

    assert tool_names == {"custom_tool_1", "custom_tool_2"}
    assert "delegate" not in tool_names
    assert "task_tool_set" not in tool_names
