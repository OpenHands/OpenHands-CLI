import json
from pathlib import Path

from pydantic import SecretStr

from openhands.sdk import Agent, LLM
from openhands_cli.locations import AGENT_SETTINGS_PATH
from openhands_cli.stores import AgentStore
from openhands_cli.utils import get_default_cli_agent
from tests.conftest import MockLocations


def read_agent_settings(persistence_dir: Path) -> dict:
    return json.loads((persistence_dir / AGENT_SETTINGS_PATH).read_text())


class TestAgentSettingsPersistence:
    def test_save_writes_only_cli_contract_fields(self, mock_locations: MockLocations):
        store = AgentStore()
        llm = LLM(
            model="stored-model",
            api_key=SecretStr("stored-key"),
            usage_id="agent",
            num_retries=123,
        )
        agent = get_default_cli_agent(llm)

        store.save(agent)

        payload = read_agent_settings(mock_locations.persistence_dir)
        assert payload["schema_version"] == 1
        assert payload["model"] == "stored-model"
        assert payload["api_key"] == "stored-key"
        assert "base_url" not in payload
        assert "tools" not in payload
        assert "llm" not in payload
        assert "memory_condensation_enabled" not in payload

    def test_load_reconstructs_agent_using_sdk_defaults_for_unsaved_fields(
        self, mock_locations: MockLocations
    ) -> None:
        store = AgentStore()

        llm = LLM(
            model="stored-model",
            api_key=SecretStr("stored-key"),
            usage_id="agent",
            num_retries=123,
        )
        agent = Agent(llm=llm, tools=[])
        store.save(agent)

        loaded = store.load_from_disk()
        assert loaded is not None

        # Explicitly persisted fields should match.
        assert loaded.llm.model == "stored-model"
        assert loaded.llm.api_key is not None
        assert loaded.llm.api_key.get_secret_value() == "stored-key"

        # Non-persisted fields should fall back to current SDK defaults.
        assert loaded.llm.num_retries == LLM.model_fields["num_retries"].default

    def test_legacy_agent_dump_is_migrated_to_settings_schema(
        self, mock_locations: MockLocations
    ) -> None:
        store = AgentStore()

        legacy_agent = Agent(
            llm=LLM(
                model="legacy-model",
                api_key=SecretStr("legacy-key"),
                base_url="https://legacy.example/",
                usage_id="agent",
            ),
            tools=[],
        )
        legacy_path = mock_locations.persistence_dir / AGENT_SETTINGS_PATH
        legacy_path.write_text(
            legacy_agent.model_dump_json(context={"expose_secrets": True})
        )

        loaded = store.load_from_disk()
        assert loaded is not None
        assert loaded.llm.model == "legacy-model"

        migrated_payload = read_agent_settings(mock_locations.persistence_dir)
        assert migrated_payload["schema_version"] == 1
        assert migrated_payload["model"] == "legacy-model"
        assert migrated_payload["api_key"] == "legacy-key"
        assert migrated_payload["base_url"] == "https://legacy.example/"
        assert "tools" not in migrated_payload
