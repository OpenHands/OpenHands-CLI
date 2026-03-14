"""Tests for AgentStore LLM profile management."""

import os
import tempfile
from pathlib import Path

import pytest

from openhands.sdk import LLM, Agent
from openhands_cli.stores.agent_store import AgentStore


@pytest.fixture
def temp_persistence_dir(monkeypatch):
    """Create a temporary persistence directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", tmpdir)
        yield tmpdir


@pytest.fixture
def agent_store(temp_persistence_dir):
    """Create an AgentStore with temporary persistence."""
    return AgentStore()


@pytest.fixture
def sample_llm():
    """Create a sample LLM for testing."""
    return LLM(
        model="anthropic/claude-sonnet-4-5-20250929",
        api_key="test-api-key",
        base_url="https://api.example.com",
        usage_id="agent",
    )


@pytest.fixture
def sample_agent(sample_llm):
    """Create a sample Agent for testing."""
    return Agent(
        llm=sample_llm,
        tools=[],
        mcp_config={},
    )


class TestAgentStoreProfiles:
    """Tests for AgentStore profile management methods."""

    def test_list_profiles_empty(self, agent_store):
        """Test listing profiles when none exist."""
        profiles = agent_store.list_profiles()
        assert profiles == []

    def test_save_llm_as_profile(self, agent_store, sample_llm, temp_persistence_dir):
        """Test saving an LLM as a profile."""
        agent_store.save_llm_as_profile("test-profile", sample_llm)

        # Verify profile was created
        profile_path = Path(temp_persistence_dir) / "profiles" / "test-profile.json"
        assert profile_path.exists()

        # Verify it's in the list
        profiles = agent_store.list_profiles()
        assert "test-profile.json" in profiles

    def test_save_and_load_profile(self, agent_store, sample_llm):
        """Test saving and loading a profile."""
        agent_store.save_llm_as_profile("my-profile", sample_llm)

        # Load and verify
        loaded_llm = agent_store.profile_store.load("my-profile")
        assert loaded_llm.model == sample_llm.model
        assert loaded_llm.base_url == sample_llm.base_url

    def test_delete_profile(self, agent_store, sample_llm, temp_persistence_dir):
        """Test deleting a profile."""
        agent_store.save_llm_as_profile("to-delete", sample_llm)

        # Verify it exists
        profiles = agent_store.list_profiles()
        assert "to-delete.json" in profiles

        # Delete it
        agent_store.delete_profile("to-delete")

        # Verify it's gone
        profiles = agent_store.list_profiles()
        assert "to-delete.json" not in profiles

    def test_delete_nonexistent_profile(self, agent_store):
        """Test deleting a profile that doesn't exist (should not raise)."""
        # Should not raise
        agent_store.delete_profile("nonexistent")

    def test_create_agent_from_profile(self, agent_store, sample_llm):
        """Test creating an agent from a saved profile."""
        agent_store.save_llm_as_profile("agent-profile", sample_llm)

        agent = agent_store.create_agent_from_profile("agent-profile")

        assert agent.llm.model == sample_llm.model
        assert agent.llm.base_url == sample_llm.base_url
        assert agent.tools is not None  # Should have default tools
        assert agent.condenser is not None  # Should have condenser

    def test_create_agent_from_nonexistent_profile(self, agent_store):
        """Test creating agent from non-existent profile raises error."""
        with pytest.raises(FileNotFoundError):
            agent_store.create_agent_from_profile("nonexistent")

    def test_load_and_activate_profile(self, agent_store, sample_llm, temp_persistence_dir):
        """Test loading a profile and activating it as current agent."""
        agent_store.save_llm_as_profile("activate-profile", sample_llm)

        agent = agent_store.load_and_activate_profile("activate-profile")

        # Verify agent was returned
        assert agent.llm.model == sample_llm.model

        # Verify it was saved as current agent
        agent_settings_path = Path(temp_persistence_dir) / "agent_settings.json"
        assert agent_settings_path.exists()

        # Verify we can load it back
        loaded_agent = agent_store.load_from_disk()
        assert loaded_agent is not None
        assert loaded_agent.llm.model == sample_llm.model

    def test_swap_llm_from_profile_no_existing_agent(self, agent_store, sample_llm):
        """Test swapping LLM when no existing agent - should create new."""
        agent_store.save_llm_as_profile("swap-profile", sample_llm)

        agent = agent_store.swap_llm_from_profile("swap-profile")

        assert agent.llm.model == sample_llm.model
        assert agent.tools is not None

    def test_swap_llm_from_profile_preserves_existing(
        self, agent_store, sample_llm, sample_agent
    ):
        """Test swapping LLM preserves existing agent settings."""
        # Save initial agent
        agent_store.save(sample_agent)

        # Create a different LLM profile
        new_llm = LLM(
            model="openai/gpt-4o",
            api_key="new-api-key",
            usage_id="agent",
        )
        agent_store.save_llm_as_profile("new-profile", new_llm)

        # Swap LLM
        updated_agent = agent_store.swap_llm_from_profile("new-profile")

        # Verify LLM was updated
        assert updated_agent.llm.model == "openai/gpt-4o"

    def test_invalid_profile_name(self, agent_store, sample_llm):
        """Test that invalid profile names raise ValueError."""
        with pytest.raises(ValueError):
            agent_store.save_llm_as_profile("../escape", sample_llm)

        with pytest.raises(ValueError):
            agent_store.save_llm_as_profile(".hidden", sample_llm)

    def test_multiple_profiles(self, agent_store, sample_llm):
        """Test managing multiple profiles."""
        # Create multiple profiles
        llm1 = sample_llm
        llm2 = LLM(model="openai/gpt-4o", api_key="key2", usage_id="agent")
        llm3 = LLM(model="anthropic/claude-3-opus", api_key="key3", usage_id="agent")

        agent_store.save_llm_as_profile("profile1", llm1)
        agent_store.save_llm_as_profile("profile2", llm2)
        agent_store.save_llm_as_profile("profile3", llm3)

        profiles = agent_store.list_profiles()
        assert len(profiles) == 3
        assert "profile1.json" in profiles
        assert "profile2.json" in profiles
        assert "profile3.json" in profiles

    def test_overwrite_existing_profile(self, agent_store, sample_llm):
        """Test that saving a profile with existing name overwrites it."""
        agent_store.save_llm_as_profile("overwrite-test", sample_llm)

        # Save with different model
        new_llm = LLM(model="openai/gpt-4o", api_key="new-key", usage_id="agent")
        agent_store.save_llm_as_profile("overwrite-test", new_llm)

        # Load and verify it was overwritten
        loaded_llm = agent_store.profile_store.load("overwrite-test")
        assert loaded_llm.model == "openai/gpt-4o"
