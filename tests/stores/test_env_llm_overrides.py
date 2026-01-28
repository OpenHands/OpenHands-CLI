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
    MissingEnvironmentVariablesError,
    apply_llm_overrides,
    check_and_warn_env_vars,
)


class TestLLMEnvOverridesFromEnv:
    """Tests for LLMEnvOverrides.from_env() factory method."""

    def test_env_vars_ignored_when_disabled(self) -> None:
        """Env vars should be ignored when enabled=False."""
        env_vars = {
            ENV_LLM_API_KEY: "env-api-key",
            ENV_LLM_BASE_URL: "https://env.url/",
            ENV_LLM_MODEL: "env-model",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            overrides = LLMEnvOverrides.from_env(enabled=False)
            assert overrides.api_key is None
            assert overrides.base_url is None
            assert overrides.model is None

    def test_env_vars_loaded_when_enabled(self) -> None:
        """Env vars should be loaded when enabled=True."""
        env_vars = {
            ENV_LLM_API_KEY: "env-api-key",
            ENV_LLM_BASE_URL: "https://env.url/",
            ENV_LLM_MODEL: "env-model",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            overrides = LLMEnvOverrides.from_env(enabled=True)
            assert overrides.api_key is not None
            assert overrides.api_key.get_secret_value() == "env-api-key"
            assert overrides.base_url == "https://env.url/"
            assert overrides.model == "env-model"

    def test_default_is_disabled(self) -> None:
        """from_env() should default to enabled=False."""
        env_vars = {
            ENV_LLM_API_KEY: "env-api-key",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            overrides = LLMEnvOverrides.from_env()
            assert overrides.api_key is None


class TestCheckAndWarnEnvVars:
    """Tests for check_and_warn_env_vars function."""

    def test_no_warning_when_no_env_vars(self, capsys) -> None:
        """Should not warn when no env vars are set."""
        with patch.dict(os.environ, {}, clear=True):
            for key in [ENV_LLM_API_KEY, ENV_LLM_BASE_URL, ENV_LLM_MODEL]:
                os.environ.pop(key, None)
            check_and_warn_env_vars()
            captured = capsys.readouterr()
            assert "Warning" not in captured.err

    def test_warning_when_env_vars_set(self, capsys) -> None:
        """Should warn when env vars are set but not used."""
        env_vars = {
            ENV_LLM_API_KEY: "test-key",
            ENV_LLM_MODEL: "test-model",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            check_and_warn_env_vars()
            captured = capsys.readouterr()
            assert "Warning" in captured.err
            assert "LLM_API_KEY" in captured.err
            assert "LLM_MODEL" in captured.err
            assert "--override-with-envs" in captured.err


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

    def test_from_env_with_no_env_vars(self) -> None:
        """from_env should return empty overrides when no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            for key in [ENV_LLM_API_KEY, ENV_LLM_BASE_URL, ENV_LLM_MODEL]:
                os.environ.pop(key, None)
            overrides = LLMEnvOverrides.from_env(enabled=True)
            assert overrides.api_key is None
            assert overrides.base_url is None
            assert overrides.model is None

    def test_from_env_with_all_env_vars(self) -> None:
        """from_env should read all env vars when enabled."""
        env_vars = {
            ENV_LLM_API_KEY: "env-api-key",
            ENV_LLM_BASE_URL: "https://env.url/",
            ENV_LLM_MODEL: "env-model",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            overrides = LLMEnvOverrides.from_env(enabled=True)
            assert overrides.api_key is not None
            assert overrides.api_key.get_secret_value() == "env-api-key"
            assert overrides.base_url == "https://env.url/"
            assert overrides.model == "env-model"

    def test_from_env_ignores_empty_strings(self) -> None:
        """from_env should treat empty env var strings as None."""
        env_vars = {
            ENV_LLM_API_KEY: "",
            ENV_LLM_BASE_URL: "https://valid.url/",
            ENV_LLM_MODEL: "",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            overrides = LLMEnvOverrides.from_env(enabled=True)
            assert overrides.api_key is None
            assert overrides.base_url == "https://valid.url/"
            assert overrides.model is None

    def test_explicit_constructor_values(self) -> None:
        """Constructor should allow explicit values."""
        overrides = LLMEnvOverrides(
            api_key=SecretStr("explicit-key"),
            model="explicit-model",
        )
        # Explicit values should be used
        assert overrides.api_key is not None
        assert overrides.api_key.get_secret_value() == "explicit-key"
        assert overrides.model == "explicit-model"


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
    """Integration tests for AgentStore.load_or_create() with env var overrides."""

    def test_env_vars_ignored_when_disabled(self, setup_test_agent_config) -> None:
        """Environment variables should be ignored when env_overrides_enabled=False."""
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

        # Set environment variables but don't enable overrides
        env_vars = {
            ENV_LLM_API_KEY: "env-api-key",
            ENV_LLM_BASE_URL: "https://env-override.url/",
            ENV_LLM_MODEL: "env-override-model",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            loaded_agent = store.load_or_create(env_overrides_enabled=False)

            assert loaded_agent is not None
            # Should use stored values, not env vars
            assert loaded_agent.llm.api_key is not None
            assert isinstance(loaded_agent.llm.api_key, SecretStr)
            assert loaded_agent.llm.api_key.get_secret_value() == "stored-api-key"
            assert loaded_agent.llm.base_url == "https://stored.url/"
            assert loaded_agent.llm.model == "stored-model"

    def test_env_vars_override_stored_settings_when_enabled(
        self, setup_test_agent_config, tmp_path_factory
    ) -> None:
        """Environment variables should override stored agent settings when enabled."""
        from openhands_cli.stores import AgentStore

        # Set environment variables
        env_vars = {
            ENV_LLM_API_KEY: "env-api-key",
            ENV_LLM_BASE_URL: "https://env-override.url/",
            ENV_LLM_MODEL: "env-override-model",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            store = AgentStore()
            agent = store.load_or_create(env_overrides_enabled=True)

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

        # Only set the model env var, clear other LLM env vars
        env_patch = {
            ENV_LLM_MODEL: "partial-override-model",
            ENV_LLM_API_KEY: "",  # Clear any existing API key env var
            ENV_LLM_BASE_URL: "",  # Clear any existing base URL env var
        }
        with patch.dict(os.environ, env_patch, clear=False):
            loaded_agent = store.load_or_create(env_overrides_enabled=True)

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

        # Load with env override enabled
        with patch.dict(os.environ, {ENV_LLM_MODEL: "temp-override-model"}):
            agent_with_override = store.load_or_create(env_overrides_enabled=True)
            assert agent_with_override is not None
            assert agent_with_override.llm.model == "temp-override-model"

        # Reload without overrides - should get original stored value
        original_env = os.environ.copy()
        for key in [ENV_LLM_API_KEY, ENV_LLM_BASE_URL, ENV_LLM_MODEL]:
            original_env.pop(key, None)

        with patch.dict(os.environ, original_env, clear=True):
            agent_without_override = store.load_or_create(env_overrides_enabled=False)
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
            loaded_agent = store.load_or_create(env_overrides_enabled=True)

            assert loaded_agent is not None
            assert loaded_agent.condenser is not None
            assert isinstance(loaded_agent.condenser, LLMSummarizingCondenser)

            # Condenser LLM should have the env overrides applied
            assert loaded_agent.condenser.llm.api_key is not None
            assert isinstance(loaded_agent.condenser.llm.api_key, SecretStr)
            assert loaded_agent.condenser.llm.api_key.get_secret_value() == "env-key"
            assert loaded_agent.condenser.llm.model == "env-model"


class TestAgentCreationFromEnvVars:
    """Tests for creating agents from environment variables without settings file."""

    def test_agent_created_with_all_env_vars(self, tmp_path) -> None:
        """Agent should be created from env vars when all LLM env vars are set."""
        from openhands_cli.stores import AgentStore

        conversations_dir = tmp_path / "conversations"
        conversations_dir.mkdir(exist_ok=True)

        env_vars = {
            ENV_LLM_API_KEY: "test-api-key",
            ENV_LLM_BASE_URL: "https://test.example.com/",
            ENV_LLM_MODEL: "test-model",
        }

        with (
            patch(
                "openhands_cli.stores.agent_store.get_persistence_dir",
                return_value=str(tmp_path),
            ),
            patch(
                "openhands_cli.stores.agent_store.get_conversations_dir",
                return_value=str(conversations_dir),
            ),
            patch.dict(os.environ, env_vars, clear=False),
        ):
            store = AgentStore()
            agent = store.load_or_create(env_overrides_enabled=True)

            assert agent is not None
            assert agent.llm.api_key is not None
            assert isinstance(agent.llm.api_key, SecretStr)
            assert agent.llm.api_key.get_secret_value() == "test-api-key"
            assert agent.llm.base_url == "https://test.example.com/"
            assert agent.llm.model == "test-model"

    def test_agent_raises_error_when_model_not_set(self, tmp_path) -> None:
        """Agent creation should raise error when LLM_MODEL env var is not set."""
        from openhands_cli.stores import AgentStore, MissingEnvironmentVariablesError

        conversations_dir = tmp_path / "conversations"
        conversations_dir.mkdir(exist_ok=True)

        # Only set API key, not model
        env_vars = {
            ENV_LLM_API_KEY: "test-api-key",
        }

        with (
            patch(
                "openhands_cli.stores.agent_store.get_persistence_dir",
                return_value=str(tmp_path),
            ),
            patch(
                "openhands_cli.stores.agent_store.get_conversations_dir",
                return_value=str(conversations_dir),
            ),
            patch.dict(os.environ, env_vars, clear=False),
        ):
            # Clear any existing LLM_MODEL env var
            os.environ.pop(ENV_LLM_MODEL, None)
            os.environ.pop(ENV_LLM_BASE_URL, None)

            store = AgentStore()

            with pytest.raises(MissingEnvironmentVariablesError) as exc_info:
                store.load_or_create(env_overrides_enabled=True)

            assert ENV_LLM_MODEL in exc_info.value.missing_vars
            assert ENV_LLM_API_KEY not in exc_info.value.missing_vars

    def test_agent_raises_error_when_api_key_not_set(self, tmp_path) -> None:
        """Agent creation should raise error when LLM_API_KEY is not set."""
        from openhands_cli.stores import AgentStore, MissingEnvironmentVariablesError

        conversations_dir = tmp_path / "conversations"
        conversations_dir.mkdir(exist_ok=True)

        # Set model but not API key
        env_vars = {
            ENV_LLM_MODEL: "test-model",
        }

        with (
            patch(
                "openhands_cli.stores.agent_store.get_persistence_dir",
                return_value=str(tmp_path),
            ),
            patch(
                "openhands_cli.stores.agent_store.get_conversations_dir",
                return_value=str(conversations_dir),
            ),
            patch.dict(os.environ, env_vars, clear=False),
        ):
            # Ensure LLM_API_KEY is not set
            os.environ.pop(ENV_LLM_API_KEY, None)

            store = AgentStore()

            with pytest.raises(MissingEnvironmentVariablesError) as exc_info:
                store.load_or_create(env_overrides_enabled=True)

            assert ENV_LLM_API_KEY in exc_info.value.missing_vars
            assert ENV_LLM_MODEL not in exc_info.value.missing_vars

    def test_agent_raises_error_when_both_api_key_and_model_not_set(
        self, tmp_path
    ) -> None:
        """Agent creation should raise error listing both missing vars."""
        from openhands_cli.stores import AgentStore, MissingEnvironmentVariablesError

        conversations_dir = tmp_path / "conversations"
        conversations_dir.mkdir(exist_ok=True)

        with (
            patch(
                "openhands_cli.stores.agent_store.get_persistence_dir",
                return_value=str(tmp_path),
            ),
            patch(
                "openhands_cli.stores.agent_store.get_conversations_dir",
                return_value=str(conversations_dir),
            ),
        ):
            # Ensure both env vars are not set
            os.environ.pop(ENV_LLM_API_KEY, None)
            os.environ.pop(ENV_LLM_MODEL, None)

            store = AgentStore()

            with pytest.raises(MissingEnvironmentVariablesError) as exc_info:
                store.load_or_create(env_overrides_enabled=True)

            assert ENV_LLM_API_KEY in exc_info.value.missing_vars
            assert ENV_LLM_MODEL in exc_info.value.missing_vars

    def test_agent_returns_none_when_env_overrides_disabled(self, tmp_path) -> None:
        """Agent creation should return None when env_overrides_enabled=False."""
        from openhands_cli.stores import AgentStore

        conversations_dir = tmp_path / "conversations"
        conversations_dir.mkdir(exist_ok=True)

        env_vars = {
            ENV_LLM_API_KEY: "test-api-key",
        }

        with (
            patch(
                "openhands_cli.stores.agent_store.get_persistence_dir",
                return_value=str(tmp_path),
            ),
            patch(
                "openhands_cli.stores.agent_store.get_conversations_dir",
                return_value=str(conversations_dir),
            ),
            patch.dict(os.environ, env_vars, clear=False),
        ):
            store = AgentStore()
            agent = store.load_or_create(env_overrides_enabled=False)

            # Should return None since env overrides are disabled
            assert agent is None


class TestCriticBehaviorInAgentCreation:
    """Tests for critic behavior when creating agents."""

    def test_critic_disabled_when_param_is_true(self, tmp_path) -> None:
        """Critic should be None when critic_disabled=True."""
        from openhands_cli.stores import AgentStore

        conversations_dir = tmp_path / "conversations"
        conversations_dir.mkdir(exist_ok=True)

        env_vars = {
            ENV_LLM_API_KEY: "test-api-key",
            ENV_LLM_MODEL: "test-model",
        }

        with (
            patch(
                "openhands_cli.stores.agent_store.get_persistence_dir",
                return_value=str(tmp_path),
            ),
            patch(
                "openhands_cli.stores.agent_store.get_conversations_dir",
                return_value=str(conversations_dir),
            ),
            patch.dict(os.environ, env_vars, clear=False),
        ):
            store = AgentStore()
            agent = store.load_or_create(
                env_overrides_enabled=True, critic_disabled=True
            )

            assert agent is not None
            # Critic should be None when disabled
            assert agent.critic is None

    def test_critic_enabled_when_param_is_false(self, tmp_path) -> None:
        """Critic should NOT be None when critic_disabled=False and settings allow."""
        from openhands_cli.stores import AgentStore
        from openhands_cli.stores.cli_settings import CliSettings

        conversations_dir = tmp_path / "conversations"
        conversations_dir.mkdir(exist_ok=True)

        env_vars = {
            ENV_LLM_API_KEY: "test-api-key",
            ENV_LLM_MODEL: "test-model",
            # Critic requires a matching base_url pattern (llm-proxy.*.all-hands.dev)
            ENV_LLM_BASE_URL: "https://llm-proxy.app.all-hands.dev/",
        }

        # Mock CliSettings to enable critic
        mock_settings = CliSettings(enable_critic=True)

        with (
            patch(
                "openhands_cli.stores.agent_store.get_persistence_dir",
                return_value=str(tmp_path),
            ),
            patch(
                "openhands_cli.stores.agent_store.get_conversations_dir",
                return_value=str(conversations_dir),
            ),
            patch.dict(os.environ, env_vars, clear=False),
            patch.object(CliSettings, "load", return_value=mock_settings),
        ):
            store = AgentStore()
            agent = store.load_or_create(
                env_overrides_enabled=True, critic_disabled=False
            )

            assert agent is not None
            # Critic should be enabled (not None) when disabled=False
            assert agent.critic is not None


class TestMissingEnvironmentVariablesError:
    """Tests for MissingEnvironmentVariablesError exception."""

    def test_error_message_contains_missing_vars(self) -> None:
        """Error message should list the missing variables."""
        error = MissingEnvironmentVariablesError([ENV_LLM_API_KEY, ENV_LLM_MODEL])
        error_str = str(error)

        assert ENV_LLM_API_KEY in error_str
        assert ENV_LLM_MODEL in error_str
        assert "Missing required environment variable(s)" in error_str

    def test_error_message_contains_instructions(self) -> None:
        """Error message should contain instructions for setting env vars."""
        error = MissingEnvironmentVariablesError([ENV_LLM_API_KEY])
        error_str = str(error)

        assert "--override-with-envs" in error_str
        assert "LLM_API_KEY" in error_str
        assert "LLM_MODEL" in error_str

    def test_missing_vars_attribute(self) -> None:
        """Error should have missing_vars attribute."""
        missing = [ENV_LLM_API_KEY, ENV_LLM_MODEL]
        error = MissingEnvironmentVariablesError(missing)

        assert error.missing_vars == missing

    def test_single_missing_var(self) -> None:
        """Error should work with a single missing variable."""
        error = MissingEnvironmentVariablesError([ENV_LLM_MODEL])
        error_str = str(error)

        assert ENV_LLM_MODEL in error_str
        assert "Missing required environment variable(s)" in error_str
