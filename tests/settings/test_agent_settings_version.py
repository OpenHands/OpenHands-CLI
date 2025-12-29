"""Tests for agent settings versioning and migration."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from openhands_cli.stores.agent_store import (
    AGENT_SETTINGS_VERSION,
    AgentStore,
    _serialize_agent_minimal,
)


@pytest.fixture
def mock_file_store():
    """Create a mock file store."""
    return MagicMock()


@pytest.fixture
def agent_store(mock_file_store):
    """Create an AgentStore with mocked file store."""
    store = AgentStore()
    store.file_store = mock_file_store
    return store


class TestSerializeAgentMinimal:
    """Tests for _serialize_agent_minimal function."""

    def test_includes_version_field(self):
        """Test that serialized output includes _version field."""
        with patch("openhands_cli.stores.agent_store.LLM") as MockLLM:
            from openhands.sdk import Agent, LLM

            llm = LLM(model="test-model", api_key="test-key")
            agent = Agent(llm=llm)

            result = _serialize_agent_minimal(agent)
            data = json.loads(result)

            assert "_version" in data
            assert data["_version"] == AGENT_SETTINGS_VERSION

    def test_preserves_condenser_kind(self):
        """Test that condenser kind discriminator is preserved."""
        from openhands.sdk import Agent, LLM, LLMSummarizingCondenser

        llm = LLM(model="test-model", api_key="test-key")
        condenser = LLMSummarizingCondenser(llm=llm)
        agent = Agent(llm=llm, condenser=condenser)

        result = _serialize_agent_minimal(agent)
        data = json.loads(result)

        assert "condenser" in data
        assert data["condenser"]["kind"] == "LLMSummarizingCondenser"

    def test_excludes_default_values(self):
        """Test that default values are excluded from serialization."""
        from openhands.sdk import Agent, LLM, LLMSummarizingCondenser

        llm = LLM(model="test-model", api_key="test-key")
        condenser = LLMSummarizingCondenser(llm=llm)
        agent = Agent(llm=llm, condenser=condenser)

        result = _serialize_agent_minimal(agent)
        data = json.loads(result)

        # Default condenser values (max_size, keep_first) should not be present
        assert "max_size" not in data.get("condenser", {})
        assert "keep_first" not in data.get("condenser", {})

        # Default agent values should not be present
        assert "system_prompt_filename" not in data


class TestAgentStoreVersionDetection:
    """Tests for version detection in AgentStore."""

    def test_get_settings_version_returns_v0_for_missing_version(self, agent_store):
        """Test that missing _version field returns v0."""
        data = {"llm": {"model": "test"}}
        assert agent_store._get_settings_version(data) == "v0"

    def test_get_settings_version_returns_actual_version(self, agent_store):
        """Test that _version field value is returned."""
        data = {"_version": "v1", "llm": {"model": "test"}}
        assert agent_store._get_settings_version(data) == "v1"

        data = {"_version": "v2", "llm": {"model": "test"}}
        assert agent_store._get_settings_version(data) == "v2"


class TestAgentStoreLoad:
    """Tests for AgentStore.load() with version handling."""

    @patch("openhands_cli.stores.agent_store.list_enabled_servers")
    @patch("openhands_cli.stores.agent_store.load_project_skills")
    @patch("openhands_cli.stores.agent_store.get_default_tools")
    def test_load_v0_triggers_migration(
        self,
        mock_get_tools,
        mock_load_skills,
        mock_list_servers,
        agent_store,
        mock_file_store,
    ):
        """Test that loading v0 settings triggers re-save in v1 format."""
        # Setup mocks
        mock_get_tools.return_value = []
        mock_load_skills.return_value = []
        mock_list_servers.return_value = {}

        # v0 format (no _version field)
        v0_settings = json.dumps(
            {
                "llm": {
                    "model": "test-model",
                    "api_key": "test-key",
                },
            }
        )
        mock_file_store.read.return_value = v0_settings

        # Load should trigger save
        agent_store.load()

        # Verify save was called (migration)
        mock_file_store.write.assert_called_once()

        # Verify the saved data has v1 version
        saved_data = json.loads(mock_file_store.write.call_args[0][1])
        assert saved_data["_version"] == "v1"

    @patch("openhands_cli.stores.agent_store.list_enabled_servers")
    @patch("openhands_cli.stores.agent_store.load_project_skills")
    @patch("openhands_cli.stores.agent_store.get_default_tools")
    def test_load_v1_does_not_trigger_migration(
        self,
        mock_get_tools,
        mock_load_skills,
        mock_list_servers,
        agent_store,
        mock_file_store,
    ):
        """Test that loading v1 settings does not trigger re-save."""
        # Setup mocks
        mock_get_tools.return_value = []
        mock_load_skills.return_value = []
        mock_list_servers.return_value = {}

        # v1 format (with _version field)
        v1_settings = json.dumps(
            {
                "_version": "v1",
                "llm": {
                    "model": "test-model",
                    "api_key": "test-key",
                },
            }
        )
        mock_file_store.read.return_value = v1_settings

        # Load should not trigger save
        agent_store.load()

        # Verify save was NOT called
        mock_file_store.write.assert_not_called()

    @patch("openhands_cli.stores.agent_store.list_enabled_servers")
    @patch("openhands_cli.stores.agent_store.load_project_skills")
    @patch("openhands_cli.stores.agent_store.get_default_tools")
    def test_load_creates_fresh_condenser_with_sdk_defaults(
        self,
        mock_get_tools,
        mock_load_skills,
        mock_list_servers,
        agent_store,
        mock_file_store,
    ):
        """Test that loading always creates fresh condenser with SDK defaults."""
        from openhands.sdk import LLM, LLMSummarizingCondenser

        # Get actual SDK defaults by creating a fresh condenser
        test_llm = LLM(model="test", api_key="test")
        sdk_default_condenser = LLMSummarizingCondenser(llm=test_llm)
        sdk_default_max_size = sdk_default_condenser.max_size
        sdk_default_keep_first = sdk_default_condenser.keep_first

        # Setup mocks
        mock_get_tools.return_value = []
        mock_load_skills.return_value = []
        mock_list_servers.return_value = {}

        # Settings with condenser that has old/different values
        settings_with_old_condenser = json.dumps(
            {
                "_version": "v1",
                "llm": {
                    "model": "test-model",
                    "api_key": "test-key",
                },
                "condenser": {
                    "kind": "LLMSummarizingCondenser",
                    "llm": {
                        "model": "test-model",
                        "api_key": "test-key",
                    },
                    "max_size": 50,  # Old value, should be ignored
                    "keep_first": 10,  # Old value, should be ignored
                },
            }
        )
        mock_file_store.read.return_value = settings_with_old_condenser

        agent = agent_store.load()

        # Verify condenser was created with SDK defaults (not the old values)
        assert agent is not None
        assert agent.condenser is not None
        # The condenser should have SDK default values, not the old ones
        assert agent.condenser.max_size == sdk_default_max_size
        assert agent.condenser.keep_first == sdk_default_keep_first


class TestAgentStoreSave:
    """Tests for AgentStore.save() with version handling."""

    def test_save_uses_minimal_serialization(self, agent_store, mock_file_store):
        """Test that save uses _serialize_agent_minimal."""
        from openhands.sdk import Agent, LLM, LLMSummarizingCondenser

        llm = LLM(model="test-model", api_key="test-key")
        condenser = LLMSummarizingCondenser(llm=llm)
        agent = Agent(llm=llm, condenser=condenser)

        agent_store.save(agent)

        # Verify write was called
        mock_file_store.write.assert_called_once()

        # Verify the saved data has v1 version and minimal format
        saved_data = json.loads(mock_file_store.write.call_args[0][1])
        assert saved_data["_version"] == "v1"
        assert "condenser" in saved_data
        assert saved_data["condenser"]["kind"] == "LLMSummarizingCondenser"
        # Default values should not be present
        assert "max_size" not in saved_data["condenser"]
        assert "keep_first" not in saved_data["condenser"]
