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
    LLMEnvOverrides,
    apply_llm_overrides,
)


class TestLLMEnvOverrides:
    """Tests for LLMEnvOverrides Pydantic model."""

    def test_all_fields_optional(self) -> None:
        """All fields should be optional with None defaults."""
        overrides = LLMEnvOverrides()
        assert overrides.api_key is None
        assert overrides.base_url is None
        assert overrides.model is None

    def test_partial_fields(self) -> None:
        """Should allow setting only some fields."""
        overrides = LLMEnvOverrides(model="gpt-4")
        assert overrides.api_key is None
        assert overrides.base_url is None
        assert overrides.model == "gpt-4"

    def test_all_fields(self) -> None:
        """Should allow setting all fields."""
        overrides = LLMEnvOverrides(
            api_key=SecretStr("my-key"),
            base_url="https://api.example.com/",
            model="claude-3",
        )
        assert overrides.api_key is not None
        assert overrides.api_key.get_secret_value() == "my-key"
        assert overrides.base_url == "https://api.example.com/"
        assert overrides.model == "claude-3"

    def test_has_overrides_false_when_empty(self) -> None:
        """has_overrides() should return False when no fields are set."""
        overrides = LLMEnvOverrides()
        assert overrides.has_overrides() is False

    def test_has_overrides_true_when_any_field_set(self) -> None:
        """has_overrides() should return True when any field is set."""
        assert LLMEnvOverrides(api_key=SecretStr("key")).has_overrides() is True
        assert LLMEnvOverrides(base_url="url").has_overrides() is True
        assert LLMEnvOverrides(model="model").has_overrides() is True

    def test_model_dump_excludes_none_fields(self) -> None:
        """model_dump(exclude_none=True) should only include set fields."""
        overrides = LLMEnvOverrides(model="gpt-4", base_url="https://api.com/")
        result = overrides.model_dump(exclude_none=True)
        assert "api_key" not in result
        assert result["base_url"] == "https://api.com/"
        assert result["model"] == "gpt-4"

    def test_model_dump_empty_when_no_fields(self) -> None:
        """model_dump(exclude_none=True) should return empty dict when no fields set."""
        overrides = LLMEnvOverrides()
        assert overrides.model_dump(exclude_none=True) == {}

    def test_api_key_is_secret_str(self) -> None:
        """api_key should be stored as SecretStr."""
        overrides = LLMEnvOverrides(api_key=SecretStr("my-secret-key"))
        assert overrides.api_key is not None
        assert isinstance(overrides.api_key, SecretStr)
        assert overrides.api_key.get_secret_value() == "my-secret-key"

    def test_auto_loads_from_env_with_no_env_vars(self) -> None:
        """Constructor should return empty overrides when no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            for key in [ENV_LLM_API_KEY, ENV_LLM_BASE_URL, ENV_LLM_MODEL]:
                os.environ.pop(key, None)
            overrides = LLMEnvOverrides()
            assert overrides.api_key is None
            assert overrides.base_url is None
            assert overrides.model is None

    def test_auto_loads_from_env_with_all_env_vars(self) -> None:
        """Constructor should automatically read all env vars when set."""
        env_vars = {
            ENV_LLM_API_KEY: "env-api-key",
            ENV_LLM_BASE_URL: "https://env.url/",
            ENV_LLM_MODEL: "env-model",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            overrides = LLMEnvOverrides()
            assert overrides.api_key is not None
            assert overrides.api_key.get_secret_value() == "env-api-key"
            assert overrides.base_url == "https://env.url/"
            assert overrides.model == "env-model"

    def test_auto_loads_ignores_empty_strings(self) -> None:
        """Constructor should treat empty env var strings as None."""
        env_vars = {
            ENV_LLM_API_KEY: "",
            ENV_LLM_BASE_URL: "https://valid.url/",
            ENV_LLM_MODEL: "",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            overrides = LLMEnvOverrides()
            assert overrides.api_key is None
            assert overrides.base_url == "https://valid.url/"
            assert overrides.model is None

    def test_explicit_values_override_env_vars(self) -> None:
        """Explicitly provided values should take precedence over env vars."""
        env_vars = {
            ENV_LLM_API_KEY: "env-api-key",
            ENV_LLM_BASE_URL: "https://env.url/",
            ENV_LLM_MODEL: "env-model",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            overrides = LLMEnvOverrides(
                api_key=SecretStr("explicit-key"),
                model="explicit-model",
            )
            # Explicit values should be used
            assert overrides.api_key is not None
            assert overrides.api_key.get_secret_value() == "explicit-key"
            assert overrides.model == "explicit-model"
            # base_url should still come from env since not explicitly provided
            assert overrides.base_url == "https://env.url/"


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
        """Should return the same LLM when overrides has no values."""
        overrides = LLMEnvOverrides()
        result = apply_llm_overrides(base_llm, overrides)
        assert result.model == base_llm.model
        assert result.api_key == base_llm.api_key
        assert result.base_url == base_llm.base_url

    def test_overrides_api_key(self, base_llm: LLM) -> None:
        """Should override api_key when provided."""
        overrides = LLMEnvOverrides(api_key=SecretStr("new-api-key"))
        result = apply_llm_overrides(base_llm, overrides)
        assert result.api_key is not None
        assert isinstance(result.api_key, SecretStr)
        assert result.api_key.get_secret_value() == "new-api-key"
        # Other fields should remain unchanged
        assert result.model == base_llm.model
        assert result.base_url == base_llm.base_url

    def test_overrides_base_url(self, base_llm: LLM) -> None:
        """Should override base_url when provided."""
        overrides = LLMEnvOverrides(base_url="https://new.url/")
        result = apply_llm_overrides(base_llm, overrides)
        assert result.base_url == "https://new.url/"
        # Other fields should remain unchanged
        assert result.model == base_llm.model
        assert result.api_key == base_llm.api_key

    def test_overrides_model(self, base_llm: LLM) -> None:
        """Should override model when provided."""
        overrides = LLMEnvOverrides(model="new-model")
        result = apply_llm_overrides(base_llm, overrides)
        assert result.model == "new-model"
        # Other fields should remain unchanged
        assert result.api_key == base_llm.api_key
        assert result.base_url == base_llm.base_url

    def test_overrides_multiple_fields(self, base_llm: LLM) -> None:
        """Should override multiple fields when provided."""
        overrides = LLMEnvOverrides(
            api_key=SecretStr("new-key"),
            base_url="https://new.url/",
            model="new-model",
        )
        result = apply_llm_overrides(base_llm, overrides)
        assert result.api_key is not None
        assert isinstance(result.api_key, SecretStr)
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
            assert agent.llm.api_key is not None
            assert isinstance(agent.llm.api_key, SecretStr)
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
            assert loaded_agent.llm.api_key is not None
            assert isinstance(loaded_agent.llm.api_key, SecretStr)
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
            assert loaded_agent.condenser.llm.api_key is not None
            assert isinstance(loaded_agent.condenser.llm.api_key, SecretStr)
            assert loaded_agent.condenser.llm.api_key.get_secret_value() == "env-key"
            assert loaded_agent.condenser.llm.model == "env-model"
