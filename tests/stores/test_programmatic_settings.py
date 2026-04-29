"""Tests for schema-driven programmatic settings persistence."""

from typing import cast

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM
from openhands_cli.stores.agent_store import AgentStore
from openhands_cli.stores.programmatic_settings import CliProgrammaticSettings
from openhands_cli.utils import get_default_cli_agent


class TestCliProgrammaticSettings:
    """Tests for CLI programmatic settings persistence behavior."""

    def test_save_does_not_merge_api_key_from_existing_agent(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        """Saving should persist exactly the API key value on the settings object."""
        monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(tmp_path))
        store = AgentStore()
        store.save(
            get_default_cli_agent(
                llm=LLM(
                    model="openai/gpt-4o-mini",
                    api_key=SecretStr("existing-api-key"),
                    usage_id="agent",
                )
            )
        )

        loaded_settings = CliProgrammaticSettings.load(store)
        settings_without_api_key = loaded_settings.model_copy(
            update={
                "llm": loaded_settings.llm.model_copy(
                    update={
                        "api_key": None,
                        "model": "openai/gpt-4.1-mini",
                    }
                )
            }
        )

        settings_without_api_key.save(store)
        saved_agent = store.load_from_disk()

        assert saved_agent is not None
        assert saved_agent.llm.api_key is None
        assert saved_agent.llm.model == "openai/gpt-4.1-mini"

    def test_round_trip_preserves_settings_across_agent_and_cli_stores(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        """Saving and loading should preserve the combined schema-backed settings."""
        monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(tmp_path))
        store = AgentStore()
        settings = CliProgrammaticSettings()
        settings = settings.model_copy(
            update={
                "llm": settings.llm.model_copy(
                    update={
                        "model": "openai/gpt-4.1-mini",
                        "api_key": SecretStr("round-trip-api-key"),
                        "base_url": "https://example.com/v1",
                        "timeout": 42,
                    }
                ),
                "verification": settings.verification.model_copy(
                    update={
                        "critic_enabled": False,
                        "enable_iterative_refinement": True,
                        "critic_threshold": 0.85,
                        "issue_threshold": 0.65,
                        "max_refinement_iterations": 4,
                    }
                ),
                "cli": settings.cli.model_copy(
                    update={
                        "default_cells_expanded": True,
                        "auto_open_plan_panel": False,
                    }
                ),
            }
        )

        settings.save(store)
        loaded = CliProgrammaticSettings.load(store)

        assert loaded.llm.model == "openai/gpt-4.1-mini"
        assert loaded.llm.api_key is not None
        api_key = cast(SecretStr, loaded.llm.api_key)
        assert api_key.get_secret_value() == "round-trip-api-key"
        assert loaded.llm.base_url == "https://example.com/v1"
        assert loaded.llm.timeout == 42
        assert loaded.verification.critic_enabled is False
        assert loaded.verification.enable_iterative_refinement is True
        assert loaded.verification.critic_threshold == pytest.approx(0.85)
        assert loaded.verification.issue_threshold == pytest.approx(0.65)
        assert loaded.verification.max_refinement_iterations == 4
        assert loaded.cli.default_cells_expanded is True
        assert loaded.cli.auto_open_plan_panel is False
