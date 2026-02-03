import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from openhands.sdk.event import ActionEvent, MessageEvent, ObservationEvent
from openhands_cli.conversations.exporter import (
    ConversationExportError,
    export_conversation_transcript,
)
from openhands_cli.conversations.models import ConversationMetadata
from openhands_cli.conversations.protocols import ConversationStore


class InMemoryStore(ConversationStore):
    def __init__(
        self,
        events: dict[str, list],
        metadata: dict[str, ConversationMetadata | None],
    ):
        self._events = events
        self._metadata = metadata

    def list_conversations(self, limit: int = 100):
        return []

    def get_metadata(self, conversation_id: str):
        return self._metadata.get(conversation_id)

    def get_event_count(self, conversation_id: str) -> int:
        return len(self._events.get(conversation_id, []))

    def load_events(
        self,
        conversation_id: str,
        limit: int | None = None,
        start_from_newest: bool = False,
    ) -> Iterator:
        events = self._events.get(conversation_id, [])
        return iter(events)

    def exists(self, conversation_id: str) -> bool:
        return conversation_id in self._events

    def create(self, conversation_id: str | None = None) -> str:
        raise NotImplementedError


def _build_sample_events():
    message_event = MessageEvent(
        id="msg-1",
        timestamp="2026-02-03T10:00:00Z",
        source="user",
        llm_message={
            "role": "user",
            "content": [{"type": "text", "text": "Hello agent"}],
        },
    )
    action_event = ActionEvent(
        id="action-1",
        timestamp="2026-02-03T10:00:05Z",
        source="agent",
        thought=[],
        reasoning_content="Execute echo command",
        thinking_blocks=[],
        action={"command": "echo Hello agent", "kind": "TerminalAction"},
        tool_name="terminal",
        tool_call_id="tool-call-1",
        tool_call={
            "id": "tool-call-1",
            "name": "terminal",
            "arguments": "{}",
            "origin": "completion",
        },
        llm_response_id="chatcmpl-test",
        summary="Run echo",
    )
    observation_event = ObservationEvent(
        id="obs-1",
        timestamp="2026-02-03T10:00:06Z",
        source="environment",
        tool_name="terminal",
        tool_call_id="tool-call-1",
        observation={
            "content": [
                {
                    "type": "text",
                    "text": "Hello agent",
                    "cache_prompt": False,
                    "enable_truncation": True,
                }
            ],
            "is_error": False,
            "command": "echo Hello agent",
            "exit_code": 0,
            "timeout": False,
            "kind": "TerminalObservation",
        },
        action_id="action-1",
    )
    return [message_event, action_event, observation_event]


def test_exporter_writes_markdown_and_json(tmp_path):
    conversation_id = "abc123"
    events = _build_sample_events()
    metadata = ConversationMetadata(
        id=conversation_id,
        created_at=datetime(2026, 2, 3, 10, 0, tzinfo=UTC),
        title="Greeting",
    )
    store = InMemoryStore(
        events={conversation_id: events},
        metadata={conversation_id: metadata},
    )

    markdown_path = tmp_path / "conversation.md"
    json_path = tmp_path / "conversation.json"

    result = export_conversation_transcript(
        store, conversation_id, markdown_path, json_path
    )

    assert markdown_path.exists()
    md_contents = markdown_path.read_text(encoding="utf-8")
    assert "Greeting" in md_contents
    assert "Tool call" in md_contents
    assert "Observation" in md_contents

    assert json_path.exists()
    json_contents = json.loads(json_path.read_text(encoding="utf-8"))
    assert json_contents["conversation_id"] == conversation_id
    assert len(json_contents["events"]) == 3
    assert result.event_count == 3


def test_exporter_raises_when_conversation_missing(tmp_path):
    store = InMemoryStore(events={}, metadata={})
    with pytest.raises(ConversationExportError):
        export_conversation_transcript(
            store,
            "missing",
            tmp_path / "missing.md",
            tmp_path / "missing.json",
        )


def test_exporter_raises_when_no_events(tmp_path):
    conversation_id = "no-events"
    metadata = ConversationMetadata(
        id=conversation_id,
        created_at=datetime(2026, 2, 3, tzinfo=UTC),
    )
    store = InMemoryStore(
        events={conversation_id: []},
        metadata={conversation_id: metadata},
    )
    with pytest.raises(ConversationExportError):
        export_conversation_transcript(
            store,
            conversation_id,
            tmp_path / "empty.md",
            tmp_path / "empty.json",
        )
