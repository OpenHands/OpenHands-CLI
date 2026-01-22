"""Tests for preserving tools when resuming conversations."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM, Agent
from openhands.sdk.conversation.persistence_const import BASE_STATE
from openhands.sdk.tool import Tool
from openhands_cli.locations import AGENT_SETTINGS_PATH
from openhands_cli.stores import AgentStore
from openhands_cli.stores.agent_store import get_persisted_conversation_tools


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj))


def write_agent(root: Path, agent: Agent) -> None:
    (root / AGENT_SETTINGS_PATH).write_text(
        agent.model_dump_json(context={"expose_secrets": True})
    )


@pytest.fixture
def persistence_dir(tmp_path, monkeypatch) -> Path:
    """Create a temporary persistence directory."""
    root = tmp_path / "openhands"
    root.mkdir()
    monkeypatch.setattr("openhands_cli.locations.PERSISTENCE_DIR", str(root))
    monkeypatch.setattr("openhands_cli.stores.agent_store.PERSISTENCE_DIR", str(root))
    return root


@pytest.fixture
def conversations_dir(persistence_dir, monkeypatch) -> Path:
    """Create a temporary conversations directory."""
    convos = persistence_dir / "conversations"
    convos.mkdir()
    monkeypatch.setattr("openhands_cli.locations.CONVERSATIONS_DIR", str(convos))
    monkeypatch.setattr(
        "openhands_cli.stores.agent_store.CONVERSATIONS_DIR", str(convos)
    )
    return convos


@pytest.fixture
def agent_store() -> AgentStore:
    return AgentStore()


class TestGetPersistedConversationTools:
    """Tests for get_persisted_conversation_tools function."""

    def test_returns_none_when_conversation_does_not_exist(self, conversations_dir):
        """Should return None when conversation directory doesn't exist."""
        result = get_persisted_conversation_tools("nonexistent-conversation-id")
        assert result is None

    def test_returns_none_when_base_state_missing(self, conversations_dir):
        """Should return None when base_state.json is missing."""
        convo_dir = conversations_dir / "test-conversation-id"
        convo_dir.mkdir()
        # No base_state.json created

        result = get_persisted_conversation_tools("test-conversation-id")
        assert result is None

    def test_returns_none_when_base_state_invalid_json(self, conversations_dir):
        """Should return None when base_state.json contains invalid JSON."""
        convo_dir = conversations_dir / "test-conversation-id"
        convo_dir.mkdir()
        (convo_dir / BASE_STATE).write_text("not valid json")

        result = get_persisted_conversation_tools("test-conversation-id")
        assert result is None

    def test_returns_none_when_tools_empty(self, conversations_dir):
        """Should return None when tools list is empty."""
        convo_dir = conversations_dir / "test-conversation-id"
        convo_dir.mkdir()
        write_json(convo_dir / BASE_STATE, {"agent": {"tools": []}})

        result = get_persisted_conversation_tools("test-conversation-id")
        assert result is None

    def test_returns_tools_from_persisted_conversation(self, conversations_dir):
        """Should return tools from a valid persisted conversation."""
        convo_dir = conversations_dir / "test-conversation-id"
        convo_dir.mkdir()

        # Create a base_state.json with tools (without delegate)
        persisted_tools = [
            {"name": "terminal"},
            {"name": "file_editor"},
            {"name": "task_tracker"},
        ]
        write_json(
            convo_dir / BASE_STATE,
            {"agent": {"tools": persisted_tools}},
        )

        result = get_persisted_conversation_tools("test-conversation-id")
        assert result is not None
        assert len(result) == 3
        assert all(isinstance(t, Tool) for t in result)
        tool_names = {t.name for t in result}
        assert tool_names == {"terminal", "file_editor", "task_tracker"}
        # Delegate should NOT be in the tools
        assert "delegate" not in tool_names


class TestAgentStoreLoadWithConversationTools:
    """Tests for AgentStore.load() preserving conversation tools."""

    @patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
    def test_load_uses_default_tools_for_new_conversation(
        self, mock_meta, persistence_dir, conversations_dir, agent_store
    ):
        """When no conversation exists, should use default CLI tools."""
        # Create a basic agent config
        persisted_agent = Agent(
            llm=LLM(model="gpt-4", api_key=SecretStr("k"), usage_id="svc"),
            tools=[],
        )
        write_agent(persistence_dir, persisted_agent)

        # Load without session_id (new conversation)
        loaded = agent_store.load()
        assert loaded is not None

        # Should have default CLI tools including delegate
        tool_names = {t.name for t in loaded.tools}
        assert "terminal" in tool_names
        assert "file_editor" in tool_names
        assert "task_tracker" in tool_names
        assert "delegate" in tool_names

    @patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
    def test_load_uses_default_tools_for_nonexistent_conversation(
        self, mock_meta, persistence_dir, conversations_dir, agent_store
    ):
        """When session_id is provided but conversation doesn't exist, use defaults."""
        # Create a basic agent config
        persisted_agent = Agent(
            llm=LLM(model="gpt-4", api_key=SecretStr("k"), usage_id="svc"),
            tools=[],
        )
        write_agent(persistence_dir, persisted_agent)

        # Load with session_id for non-existent conversation
        loaded = agent_store.load(session_id="nonexistent-conversation-id")
        assert loaded is not None

        # Should have default CLI tools including delegate
        tool_names = {t.name for t in loaded.tools}
        assert "delegate" in tool_names

    @patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
    def test_load_preserves_tools_from_existing_conversation(
        self, mock_meta, persistence_dir, conversations_dir, agent_store
    ):
        """When resuming a conversation, should use tools from persisted state."""
        # Create a basic agent config
        persisted_agent = Agent(
            llm=LLM(model="gpt-4", api_key=SecretStr("k"), usage_id="svc"),
            tools=[],
        )
        write_agent(persistence_dir, persisted_agent)

        # Create a conversation with tools that DON'T include delegate
        convo_id = "existing-conversation-id"
        convo_dir = conversations_dir / convo_id
        convo_dir.mkdir()
        persisted_tools = [
            {"name": "terminal"},
            {"name": "file_editor"},
            {"name": "task_tracker"},
        ]
        write_json(
            convo_dir / BASE_STATE,
            {"agent": {"tools": persisted_tools}},
        )

        # Load with session_id for existing conversation
        loaded = agent_store.load(session_id=convo_id)
        assert loaded is not None

        # Should have tools from persisted conversation (NO delegate)
        tool_names = {t.name for t in loaded.tools}
        assert tool_names == {"terminal", "file_editor", "task_tracker"}
        assert "delegate" not in tool_names

    @patch("openhands_cli.stores.agent_store.get_llm_metadata", return_value={})
    def test_load_preserves_delegate_if_conversation_had_it(
        self, mock_meta, persistence_dir, conversations_dir, agent_store
    ):
        """When resuming a conversation that had delegate, should preserve it."""
        # Create a basic agent config
        persisted_agent = Agent(
            llm=LLM(model="gpt-4", api_key=SecretStr("k"), usage_id="svc"),
            tools=[],
        )
        write_agent(persistence_dir, persisted_agent)

        # Create a conversation with tools that INCLUDE delegate
        convo_id = "conversation-with-delegate"
        convo_dir = conversations_dir / convo_id
        convo_dir.mkdir()
        persisted_tools = [
            {"name": "terminal"},
            {"name": "file_editor"},
            {"name": "task_tracker"},
            {"name": "delegate"},
        ]
        write_json(
            convo_dir / BASE_STATE,
            {"agent": {"tools": persisted_tools}},
        )

        # Load with session_id for existing conversation
        loaded = agent_store.load(session_id=convo_id)
        assert loaded is not None

        # Should have tools from persisted conversation (INCLUDING delegate)
        tool_names = {t.name for t in loaded.tools}
        assert tool_names == {"terminal", "file_editor", "task_tracker", "delegate"}
