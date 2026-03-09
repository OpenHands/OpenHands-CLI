"""Tests for schema-driven programmatic settings persistence."""

from pydantic import SecretStr

from openhands.sdk import LLM
from openhands_cli.stores.agent_store import AgentStore
from openhands_cli.stores.programmatic_settings import CliProgrammaticSettings
from openhands_cli.utils import get_default_cli_agent


class TestCliProgrammaticSettings:
    """Tests for CLI programmatic settings persistence behavior."""

    def test_save_does_not_merge_api_key_from_existing_agent(
        self,
        monkeypatch,
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
