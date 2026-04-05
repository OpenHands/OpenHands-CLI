"""Tests for tool resolution with backward compatibility for DelegateTool.

Event fixtures are derived from real conversations found in ~/.openhands/conversations/.
- Delegate conversation: 749d47ca086b4402b26e57a39135cd9c (2026-02-26)
- Non-delegate conversation: bf81e949285b4bfca1e955288e78d664 (2026-03-11)
"""

import json

import pytest

from openhands.sdk.tool import Tool
from openhands_cli.stores.agent_store import AgentStore


# -- Real event snippets extracted from persisted conversations ----------------

# From conversation 749d47ca… which used DelegateTool
DELEGATE_CONVERSATION_EVENTS = [
    {
        "id": "2e2c2ad3-1a07-4bd5-8628-53e2cba78497",
        "timestamp": "2026-02-26T09:53:26.630217",
        "source": "agent",
        "kind": "SystemPromptEvent",
    },
    {
        "id": "9d99120d-5d0c-47b3-baac-e4a5bdecfb37",
        "timestamp": "2026-02-26T09:53:26.650830",
        "source": "user",
        "kind": "MessageEvent",
    },
    {
        "id": "469b77ff-f36a-4e03-84d0-8634a4de9052",
        "timestamp": "2026-02-26T09:53:33.588179",
        "source": "agent",
        "tool_name": "delegate",
        "tool_call_id": "toolu_01S1GjX8q2LuLfBxqGJ4375z",
        "kind": "ActionEvent",
    },
    {
        "id": "d32eca24-5e31-4c16-9016-4f935f2bae2d",
        "timestamp": "2026-02-26T09:53:36.666771",
        "source": "environment",
        "tool_name": "delegate",
        "tool_call_id": "toolu_01S1GjX8q2LuLfBxqGJ4375z",
        "kind": "ObservationEvent",
    },
]

# From conversation bf81e949… which never invoked DelegateTool
NON_DELEGATE_CONVERSATION_EVENTS = [
    {
        "id": "c2dd4a86-2de0-48e6-bde2-a6f6564d925d",
        "timestamp": "2026-03-11T18:33:19.032087",
        "source": "agent",
        "kind": "SystemPromptEvent",
    },
    {
        "id": "dd76abe3-2977-4b1a-bed8-b627835bc7a0",
        "timestamp": "2026-03-11T18:33:19.051976",
        "source": "user",
        "kind": "MessageEvent",
    },
    {
        "id": "e37a78e1-55d5-4a33-b7f1-36f358012b52",
        "timestamp": "2026-03-11T18:33:22.462657",
        "source": "agent",
        "tool_name": "terminal",
        "tool_call_id": "chatcmpl-tool-8bdae665c62b1a8e",
        "kind": "ActionEvent",
    },
    {
        "id": "a056dfc4-0bce-4221-b587-fd17373039bf",
        "timestamp": "2026-03-11T18:33:24.085072",
        "source": "environment",
        "tool_name": "terminal",
        "tool_call_id": "chatcmpl-tool-8bdae665c62b1a8e",
        "kind": "ObservationEvent",
    },
]


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


def _write_events(events_dir, events):
    """Write event dicts to JSON files matching the real naming convention."""
    events_dir.mkdir(parents=True, exist_ok=True)
    for i, event in enumerate(events):
        event_file = events_dir / f"event-{i:05d}-{event['id']}.json"
        event_file.write_text(json.dumps(event))


# -- Tests using real conversation snippets ------------------------------------


@pytest.mark.parametrize(
    "session_id",
    [None, "nonexistent-conversation"],
    ids=["new_conversation", "nonexistent_conversation"],
)
def test_no_events_uses_task_tool_set(agent_store, session_id):
    """Conversations without events (new or nonexistent) use TaskToolSet."""
    tools = agent_store._resolve_tools(session_id)
    tool_names = {t.name for t in tools}
    assert "task_tool_set" in tool_names
    assert "delegate" not in tool_names


@pytest.mark.parametrize(
    ("events", "expected_tool", "unexpected_tool"),
    [
        (
            DELEGATE_CONVERSATION_EVENTS,
            "delegate",
            "task_tool_set",
        ),
        (
            NON_DELEGATE_CONVERSATION_EVENTS,
            "task_tool_set",
            "delegate",
        ),
    ],
    ids=["legacy_delegate_conversation", "modern_conversation"],
)
def test_tool_resolution_from_real_events(
    agent_store, tmp_path, events, expected_tool, unexpected_tool
):
    """Tool resolution detects DelegateTool usage from real persisted events."""
    conv_id = "test-conversation"
    events_dir = tmp_path / "conversations" / conv_id / "events"
    _write_events(events_dir, events)

    tools = agent_store._resolve_tools(conv_id)
    tool_names = {t.name for t in tools}
    assert expected_tool in tool_names
    assert unexpected_tool not in tool_names


def test_persisted_tools_take_precedence(agent_store, tmp_path, monkeypatch):
    """Tools from base_state.json take precedence over event-based detection."""
    conv_id = "persisted-conversation-789"
    events_dir = tmp_path / "conversations" / conv_id / "events"
    _write_events(events_dir, DELEGATE_CONVERSATION_EVENTS)

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
