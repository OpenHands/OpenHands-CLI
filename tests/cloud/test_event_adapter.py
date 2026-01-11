from __future__ import annotations

from openhands.sdk import MessageEvent, TextContent
from openhands_cli.cloud.event_adapter import adapt_cloud_runtime_event


def test_adapt_cloud_runtime_event_user_message() -> None:
    ev = {"source": "user", "action": "message", "args": {"content": "Hello"}}
    out = adapt_cloud_runtime_event(ev)
    assert isinstance(out, MessageEvent)
    assert out.source == "user"
    assert out.llm_message.role == "user"
    assert isinstance(out.llm_message.content[0], TextContent)
    assert out.llm_message.content[0].text == "Hello"


def test_adapt_cloud_runtime_event_agent_message() -> None:
    ev = {"source": "agent", "action": "message", "message": "Hi!"}
    out = adapt_cloud_runtime_event(ev)
    assert isinstance(out, MessageEvent)
    assert out.source == "agent"
    assert out.llm_message.role == "assistant"
    assert isinstance(out.llm_message.content[0], TextContent)
    assert out.llm_message.content[0].text == "Hi!"


def test_adapt_cloud_runtime_event_environment_is_ignored() -> None:
    ev = {"source": "environment", "action": "agent_state_changed", "args": {"x": 1}}
    assert adapt_cloud_runtime_event(ev) is None
