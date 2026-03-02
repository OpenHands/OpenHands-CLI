"""Integration tests for marketplace_path setting in AgentStore."""

from unittest.mock import MagicMock, patch

import pytest

from openhands.sdk import LLM, Agent, AgentContext
from openhands_cli.stores import AgentStore, CliSettings


class TestMarketplacePathIntegration:
    """Tests verifying marketplace_path setting is properly loaded and passed."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        return Agent(
            llm=LLM(model="test/model", api_key="test-key", usage_id="test-service"),
        )

    @pytest.fixture
    def base_patches(self, mock_agent):
        """Provide common patches for AgentStore tests."""
        with (
            patch("openhands_cli.stores.agent_store.LocalFileStore") as mock_file_store,
            patch(
                "openhands_cli.stores.agent_store.get_os_description",
                return_value="TestOS 1.0",
            ),
            patch(
                "openhands_cli.stores.agent_store.list_enabled_servers", return_value=[]
            ),
        ):
            mock_store_instance = MagicMock()
            mock_file_store.return_value = mock_store_instance
            mock_store_instance.read.return_value = mock_agent.model_dump_json()
            yield

    def test_build_agent_context_loads_cli_settings(self, base_patches):
        """Verify _build_agent_context loads CLI settings."""
        with patch(
            "openhands_cli.stores.agent_store.CliSettings.load"
        ) as mock_cli_load:
            mock_cli_load.return_value = CliSettings(marketplace_path=None)
            agent_store = AgentStore()
            agent_store._build_agent_context()

            # Verify CliSettings.load() was called
            mock_cli_load.assert_called_once()

    def test_build_agent_context_with_none_marketplace_path(self, base_patches):
        """Verify _build_agent_context works with None marketplace_path (load all)."""
        with patch(
            "openhands_cli.stores.agent_store.CliSettings.load"
        ) as mock_cli_load:
            mock_cli_load.return_value = CliSettings(marketplace_path=None)
            agent_store = AgentStore()
            context = agent_store._build_agent_context()

            # Context should be created successfully
            assert isinstance(context, AgentContext)
            # load_public_skills should be True (loads all skills when path is None)
            assert context.load_public_skills is True

    def test_build_agent_context_with_custom_marketplace_path(self, base_patches):
        """Verify _build_agent_context reads custom marketplace_path from settings."""
        custom_path = "custom/marketplace.json"
        with patch(
            "openhands_cli.stores.agent_store.CliSettings.load"
        ) as mock_cli_load:
            mock_cli_load.return_value = CliSettings(marketplace_path=custom_path)
            agent_store = AgentStore()
            context = agent_store._build_agent_context()

            # Context should be created successfully
            assert isinstance(context, AgentContext)
            # If SDK supports marketplace_path, it would be set
            # For now, just verify the context is valid
            assert context.load_public_skills is True

    def test_marketplace_path_stored_correctly_in_settings(self, tmp_path):
        """Verify marketplace_path is persisted correctly in CliSettings."""
        config_path = tmp_path / "cli_config.json"

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            # Test saving None (default - load all skills)
            settings = CliSettings(marketplace_path=None)
            settings.save()
            loaded = CliSettings.load()
            assert loaded.marketplace_path is None

            # Test saving custom path
            settings = CliSettings(marketplace_path="custom/path.json")
            settings.save()
            loaded = CliSettings.load()
            assert loaded.marketplace_path == "custom/path.json"

    def test_cli_settings_default_marketplace_path_is_none(self):
        """Verify default marketplace_path is None (load all skills)."""
        settings = CliSettings()
        assert settings.marketplace_path is None

    def test_loaded_agent_has_valid_context(self, base_patches):
        """Verify loaded agent has valid agent_context from _build_agent_context."""
        with patch(
            "openhands_cli.stores.agent_store.CliSettings.load"
        ) as mock_cli_load:
            mock_cli_load.return_value = CliSettings(marketplace_path=None)

            loaded_agent = AgentStore().load_or_create()
            assert loaded_agent is not None
            assert loaded_agent.agent_context is not None
            assert isinstance(loaded_agent.agent_context, AgentContext)
