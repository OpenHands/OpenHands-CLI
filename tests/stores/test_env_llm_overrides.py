"""Tests for environment variable LLM configuration overrides."""

import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM
from openhands_cli.stores.agent_store import (
    ENV_LLM_API_KEY,
    ENV_LLM_BASE_URL,
    ENV_LLM_MODEL,
    apply_llm_overrides,
    get_env_llm_overrides,
)


class TestGetEnvLlmOverrides:
    """Tests for get_env_llm_overrides function."""

    def test_returns_empty_dict_when_no_env_vars_set(self) -> None:
        """Should return empty dict when no LLM env vars are set."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure the specific env vars are not set
            for key in [ENV_LLM_API_KEY, ENV_LLM_BASE_URL, ENV_LLM_MODEL]:
                os.environ.pop(key, None)
            result = get_env_llm_overrides()
            assert result == {}

    def test_returns_api_key_when_set(self) -> None:
        """Should return api_key when LLM_API_KEY is set."""
        with patch.dict(
            os.environ, {ENV_LLM_API_KEY: "test-api-key-123"}, clear=False
        ):
            result = get_env_llm_overrides()
            assert "api_key" in result
            assert result["api_key"] == "test-api-key-123"

    def test_returns_base_url_when_set(self) -> None:
        """Should return base_url when LLM_BASE_URL is set."""
        with patch.dict(
            os.environ, {ENV_LLM_BASE_URL: "https://custom.api.com/"}, clear=False
        ):
            result = get_env_llm_overrides()
            assert "base_url" in result
            assert result["base_url"] == "https://custom.api.com/"

    def test_returns_model_when_set(self) -> None:
        """Should return model when LLM_MODEL is set."""
        with patch.dict(os.environ, {ENV_LLM_MODEL: "gpt-4-turbo"}, clear=False):
            result = get_env_llm_overrides()
            assert "model" in result
            assert result["model"] == "gpt-4-turbo"

    def test_returns_all_overrides_when_all_set(self) -> None:
        """Should return all overrides when all env vars are set."""
        env_vars = {
            ENV_LLM_API_KEY: "my-api-key",
            ENV_LLM_BASE_URL: "https://my-llm.com/",
            ENV_LLM_MODEL: "claude-3-opus",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            result = get_env_llm_overrides()
            assert result == {
                "api_key": "my-api-key",
                "base_url": "https://my-llm.com/",
                "model": "claude-3-opus",
            }

    def test_ignores_empty_string_values(self) -> None:
        """Should not include env vars that are set to empty strings."""
        env_vars = {
            ENV_LLM_API_KEY: "",
            ENV_LLM_BASE_URL: "https://valid.url/",
            ENV_LLM_MODEL: "",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            result = get_env_llm_overrides()
            # Only base_url should be included since others are empty
            assert result == {"base_url": "https://valid.url/"}


class TestApplyLlmOverrides:
    """Tests for apply_llm_overrides function."""

    @pytest.fixture
    def base_llm(self) -> LLM:
        """Create a base LLM instance for testing."""
        return LLM(
            model="original-model",
            api_key=SecretStr("original-api-key"),
            base_url="https://original.url/",
            usage_id="test",
        )

    def test_returns_same_llm_when_no_overrides(self, base_llm: LLM) -> None:
        """Should return the same LLM when overrides dict is empty."""
        result = apply_llm_overrides(base_llm, {})
        assert result.model == base_llm.model
        assert result.api_key == base_llm.api_key
        assert result.base_url == base_llm.base_url

    def test_overrides_api_key(self, base_llm: LLM) -> None:
        """Should override api_key when provided."""
        result = apply_llm_overrides(base_llm, {"api_key": "new-api-key"})
        assert result.api_key.get_secret_value() == "new-api-key"
        # Other fields should remain unchanged
        assert result.model == base_llm.model
        assert result.base_url == base_llm.base_url

    def test_overrides_base_url(self, base_llm: LLM) -> None:
        """Should override base_url when provided."""
        result = apply_llm_overrides(base_llm, {"base_url": "https://new.url/"})
        assert result.base_url == "https://new.url/"
        # Other fields should remain unchanged
        assert result.model == base_llm.model
        assert result.api_key == base_llm.api_key

    def test_overrides_model(self, base_llm: LLM) -> None:
        """Should override model when provided."""
        result = apply_llm_overrides(base_llm, {"model": "new-model"})
        assert result.model == "new-model"
        # Other fields should remain unchanged
        assert result.api_key == base_llm.api_key
        assert result.base_url == base_llm.base_url

    def test_overrides_multiple_fields(self, base_llm: LLM) -> None:
        """Should override multiple fields when provided."""
        overrides = {
            "api_key": "new-key",
            "base_url": "https://new.url/",
            "model": "new-model",
        }
        result = apply_llm_overrides(base_llm, overrides)
        assert result.api_key.get_secret_value() == "new-key"
        assert result.base_url == "https://new.url/"
        assert result.model == "new-model"


class TestAgentStoreEnvOverrides:
    """Integration tests for AgentStore.load() with environment variable overrides."""

    def test_env_vars_override_stored_settings(
        self, setup_test_agent_config, tmp_path_factory
    ) -> None:
        """Environment variables should override stored agent settings."""
        from openhands_cli.stores import AgentStore

        # Set environment variables
        env_vars = {
            ENV_LLM_API_KEY: "env-api-key",
            ENV_LLM_BASE_URL: "https://env-override.url/",
            ENV_LLM_MODEL: "env-override-model",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            store = AgentStore()
            agent = store.load()

            assert agent is not None
            assert agent.llm.api_key.get_secret_value() == "env-api-key"
            assert agent.llm.base_url == "https://env-override.url/"
            assert agent.llm.model == "env-override-model"

    def test_partial_env_overrides(self, setup_test_agent_config) -> None:
        """Should only override fields that have env vars set."""
        from openhands.sdk import LLM, Agent
        from openhands_cli.stores import AgentStore

        # First, save a known agent configuration
        store = AgentStore()
        llm = LLM(
            model="stored-model",
            api_key=SecretStr("stored-api-key"),
            base_url="https://stored.url/",
            usage_id="agent",
        )
        agent = Agent(llm=llm, tools=[])
        store.save(agent)

        # Only set the model env var
        with patch.dict(os.environ, {ENV_LLM_MODEL: "partial-override-model"}):
            loaded_agent = store.load()

            assert loaded_agent is not None
            # Model should be overridden
            assert loaded_agent.llm.model == "partial-override-model"
            # API key should remain from stored settings
            assert loaded_agent.llm.api_key.get_secret_value() == "stored-api-key"

    def test_env_overrides_not_persisted(self, setup_test_agent_config) -> None:
        """Environment variable overrides should NOT be persisted to disk."""
        from openhands.sdk import LLM, Agent
        from openhands_cli.stores import AgentStore

        # First, save a known agent configuration
        store = AgentStore()
        llm = LLM(
            model="original-stored-model",
            api_key=SecretStr("original-stored-key"),
            base_url="https://original-stored.url/",
            usage_id="agent",
        )
        agent = Agent(llm=llm, tools=[])
        store.save(agent)

        # Load with env override
        with patch.dict(os.environ, {ENV_LLM_MODEL: "temp-override-model"}):
            agent_with_override = store.load()
            assert agent_with_override is not None
            assert agent_with_override.llm.model == "temp-override-model"

        # Clear env vars and reload - should get original stored value
        # Remove the env var by patching with empty dict for that key
        original_env = os.environ.copy()
        for key in [ENV_LLM_API_KEY, ENV_LLM_BASE_URL, ENV_LLM_MODEL]:
            original_env.pop(key, None)

        with patch.dict(os.environ, original_env, clear=True):
            agent_without_override = store.load()
            assert agent_without_override is not None
            # Should be back to original stored model
            assert agent_without_override.llm.model == "original-stored-model"

    def test_condenser_llm_also_gets_overrides(self, setup_test_agent_config) -> None:
        """Condenser LLM should also receive environment variable overrides."""
        from openhands.sdk import LLM, Agent, LLMSummarizingCondenser
        from openhands_cli.stores import AgentStore

        # Create an agent with a condenser and save it
        store = AgentStore()
        llm = LLM(
            model="original-model",
            api_key=SecretStr("original-key"),
            base_url="https://original.url/",
            usage_id="agent",
        )
        condenser_llm = LLM(
            model="original-condenser-model",
            api_key=SecretStr("original-condenser-key"),
            base_url="https://original-condenser.url/",
            usage_id="condenser",
        )
        condenser = LLMSummarizingCondenser(llm=condenser_llm)
        agent = Agent(llm=llm, tools=[], condenser=condenser)
        store.save(agent)

        # Load with env overrides
        env_vars = {
            ENV_LLM_API_KEY: "env-key",
            ENV_LLM_MODEL: "env-model",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            loaded_agent = store.load()

            assert loaded_agent is not None
            assert loaded_agent.condenser is not None
            assert isinstance(loaded_agent.condenser, LLMSummarizingCondenser)

            # Condenser LLM should have the env overrides applied
            assert loaded_agent.condenser.llm.api_key.get_secret_value() == "env-key"
            assert loaded_agent.condenser.llm.model == "env-model"
