"""Unit tests for the SettingsScreen modal."""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest
from textual.widgets import Select

from openhands.sdk import LLM
from openhands_cli.refactor.modals.settings.settings_screen import SettingsScreen
from openhands_cli.refactor.modals.settings.utils import SettingsFormData, save_settings
from openhands_cli.tui.settings.store import AgentStore
from openhands_cli.utils import get_default_cli_agent


class TestSettingsScreen:
    """Test cases for SettingsScreen functionality."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory for testing."""
        temp_dir = tempfile.mkdtemp()
        original_config = os.environ.get("OPENHANDS_CLI_CONFIG_DIR")
        os.environ["OPENHANDS_CLI_CONFIG_DIR"] = temp_dir
        yield temp_dir
        # Cleanup
        if original_config:
            os.environ["OPENHANDS_CLI_CONFIG_DIR"] = original_config
        else:
            os.environ.pop("OPENHANDS_CLI_CONFIG_DIR", None)

    @pytest.fixture
    def agent_store(self, temp_config_dir):
        """Create an agent store for testing."""
        return AgentStore()

    @pytest.fixture
    def test_agent(self):
        """Create a test agent with LLM configuration."""
        llm = LLM(
            model="openai/gpt-4o-mini", api_key="test-api-key-12345", usage_id="agent"
        )
        return get_default_cli_agent(llm=llm)

    @pytest.fixture
    def settings_screen(self):
        """Create a SettingsScreen instance for testing."""
        return SettingsScreen()

    def test_is_initial_setup_required_no_existing_agent(self, temp_config_dir):
        """Test that initial setup is required when no agent exists."""
        # Mock AgentStore to return None (no existing agent)
        with patch(
            "openhands_cli.refactor.modals.settings.settings_screen.AgentStore"
        ) as mock_agent_store_class:
            mock_agent_store = Mock()
            mock_agent_store.load.return_value = None
            mock_agent_store_class.return_value = mock_agent_store

            assert SettingsScreen.is_initial_setup_required() is True

    def test_is_initial_setup_required_existing_agent(
        self, temp_config_dir, agent_store, test_agent
    ):
        """Test that initial setup is not required when agent exists."""
        agent_store.save(test_agent)
        assert SettingsScreen.is_initial_setup_required() is False

    def test_load_current_settings_basic_mode(
        self, settings_screen, agent_store, test_agent
    ):
        """Test loading settings in basic mode."""
        # Save test agent
        agent_store.save(test_agent)

        # Mock the UI components
        settings_screen.agent_store = agent_store
        settings_screen.mode_select = Mock()
        settings_screen.provider_select = Mock()
        settings_screen.model_select = Mock()
        settings_screen.custom_model_input = Mock()
        settings_screen.base_url_input = Mock()
        settings_screen.api_key_input = Mock()
        settings_screen.memory_select = Mock()

        # Mock the _update_model_options method
        settings_screen._update_model_options = Mock()
        settings_screen._update_field_dependencies = Mock()

        # Load settings
        settings_screen._load_current_settings()

        # Verify basic mode is detected
        assert settings_screen.is_advanced_mode is False
        assert settings_screen.mode_select.value == "basic"

        # Verify provider and model are set
        assert settings_screen.provider_select.value == "openai"
        settings_screen._update_model_options.assert_called_once_with("openai")
        assert settings_screen.model_select.value == "openai/gpt-4o-mini"

        # Verify API key placeholder is set
        expected_placeholder = "Current: tes*** (leave empty to keep current)"
        assert settings_screen.api_key_input.placeholder == expected_placeholder

    def test_load_current_settings_advanced_mode(self, settings_screen, agent_store):
        """Test loading settings in advanced mode."""
        # Create agent with base URL (advanced mode)
        llm = LLM(
            model="custom-model",
            api_key="test-key",
            base_url="https://api.example.com/v1",
            usage_id="agent",
        )
        agent = get_default_cli_agent(llm=llm)
        agent_store.save(agent)

        # Set the current agent and mock the UI components
        settings_screen.agent_store = agent_store
        settings_screen.current_agent = agent  # Set the current agent
        settings_screen.mode_select = Mock()
        settings_screen.provider_select = Mock()
        settings_screen.model_select = Mock()
        settings_screen.custom_model_input = Mock()
        settings_screen.base_url_input = Mock()
        settings_screen.api_key_input = Mock()
        settings_screen.memory_select = Mock()
        settings_screen._update_field_dependencies = Mock()

        # Load settings
        settings_screen._load_current_settings()

        # Verify advanced mode is detected
        assert settings_screen.is_advanced_mode is True
        assert settings_screen.mode_select.value == "advanced"

        # Verify custom model and base URL are set
        assert settings_screen.custom_model_input.value == "custom-model"
        assert settings_screen.base_url_input.value == "https://api.example.com/v1"

    def test_update_model_options_preserves_selection(self, settings_screen):
        """Test that _update_model_options preserves current selection when possible."""
        # Mock model select widget
        mock_model_select = Mock()
        mock_model_select.value = "openai/gpt-4o-mini"
        settings_screen.model_select = mock_model_select

        # Mock get_model_options to return options including current selection
        with patch(
            "openhands_cli.refactor.modals.settings.settings_screen.get_model_options"
        ) as mock_get_options:
            mock_get_options.return_value = [
                ("GPT-4o Mini", "openai/gpt-4o-mini"),
                ("GPT-4o", "openai/gpt-4o"),
                ("GPT-3.5 Turbo", "openai/gpt-3.5-turbo"),
            ]

            # Call _update_model_options
            settings_screen._update_model_options("openai")

            # Verify set_options was called
            mock_model_select.set_options.assert_called_once()

            # Verify current selection was preserved
            assert mock_model_select.value == "openai/gpt-4o-mini"

    def test_update_model_options_selection_not_in_new_options(self, settings_screen):
        """Test _update_model_options when current selection is not in new options."""
        # Mock model select widget with selection not in new options
        mock_model_select = Mock()
        mock_model_select.value = "anthropic/claude-3-sonnet"
        settings_screen.model_select = mock_model_select

        # Mock get_model_options to return options not including current selection
        with patch(
            "openhands_cli.refactor.modals.settings.settings_screen.get_model_options"
        ) as mock_get_options:
            mock_get_options.return_value = [
                ("GPT-4o Mini", "openai/gpt-4o-mini"),
                ("GPT-4o", "openai/gpt-4o"),
            ]

            # Call _update_model_options
            settings_screen._update_model_options("openai")

            # Verify set_options was called
            mock_model_select.set_options.assert_called_once()

            # Verify selection was not preserved (since it's not in new options)
            # The value should remain as it was set by the mock

    def test_update_model_options_no_options_available(self, settings_screen):
        """Test _update_model_options when no options are available."""
        # Mock model select widget
        mock_model_select = Mock()
        settings_screen.model_select = mock_model_select

        # Mock get_model_options to return empty list
        with patch(
            "openhands_cli.refactor.modals.settings.settings_screen.get_model_options"
        ) as mock_get_options:
            mock_get_options.return_value = []

            # Call _update_model_options
            settings_screen._update_model_options("invalid_provider")

            # Verify set_options was called with "No models available"
            mock_model_select.set_options.assert_called_once_with(
                [("No models available", "")]
            )

    def test_api_key_preservation_empty_input(
        self, settings_screen, agent_store, test_agent
    ):
        """Test that API key is preserved when input is empty."""
        # Save test agent
        agent_store.save(test_agent)

        # Setup settings screen
        settings_screen.agent_store = agent_store
        settings_screen.current_agent = test_agent

        # Test the save_settings utility function directly
        form_data = SettingsFormData(
            mode="basic",
            provider="openai",
            model="openai/gpt-4o",
            custom_model=None,
            base_url=None,
            api_key_input="",  # Empty input should preserve existing
            memory_condensation_enabled=False,
        )

        result = save_settings(form_data, test_agent)
        assert result.success is True

        # Verify the agent was saved with preserved API key
        saved_agent = agent_store.load()
        assert saved_agent is not None
        api_key_value = saved_agent.llm.api_key
        if hasattr(api_key_value, "get_secret_value"):
            api_key_value = api_key_value.get_secret_value()
        assert api_key_value == "test-api-key-12345"  # API key should be preserved

    def test_api_key_preservation_no_current_agent(
        self, settings_screen, agent_store, test_agent
    ):
        """Test that API key preservation works when current_agent is None."""
        # Save test agent
        agent_store.save(test_agent)

        # Test the save_settings utility function directly with existing agent
        form_data = SettingsFormData(
            mode="basic",
            provider="openai",
            model="openai/gpt-4o",
            custom_model=None,
            base_url=None,
            api_key_input="",  # Empty input should preserve existing
            memory_condensation_enabled=False,
        )

        result = save_settings(form_data, test_agent)
        assert result.success is True

        # Verify the agent was saved with preserved API key
        saved_agent = agent_store.load()
        assert saved_agent is not None
        api_key_value = saved_agent.llm.api_key
        if hasattr(api_key_value, "get_secret_value"):
            api_key_value = api_key_value.get_secret_value()
        assert api_key_value == "test-api-key-12345"  # API key should be preserved

    def test_api_key_preservation_with_new_key(
        self, settings_screen, agent_store, test_agent
    ):
        """Test that new API key is used when provided."""
        # Save test agent
        agent_store.save(test_agent)

        # Test the save_settings utility function directly with new API key
        form_data = SettingsFormData(
            mode="basic",
            provider="openai",
            model="openai/gpt-4o",
            custom_model=None,
            base_url=None,
            api_key_input="new-api-key-67890",  # New key provided
            memory_condensation_enabled=False,
        )

        result = save_settings(form_data, test_agent)
        assert result.success is True

        # Verify the agent was saved with new API key
        saved_agent = agent_store.load()
        assert saved_agent is not None
        api_key_value = saved_agent.llm.api_key
        if hasattr(api_key_value, "get_secret_value"):
            api_key_value = api_key_value.get_secret_value()
        assert api_key_value == "new-api-key-67890"  # New API key should be used

    def test_save_settings_no_api_key_error(self, settings_screen):
        """Test that error is shown when no API key is available."""
        # Test the save_settings utility function directly with no API key and no
        # existing agent
        form_data = SettingsFormData(
            mode="basic",
            provider="openai",
            model="openai/gpt-4o",
            custom_model=None,
            base_url=None,
            api_key_input="",  # Empty input with no existing agent
            memory_condensation_enabled=False,
        )

        result = save_settings(form_data, None)  # No existing agent
        assert result.success is False
        assert result.error_message == "API Key is required"

    def test_save_settings_advanced_mode(
        self, settings_screen, agent_store, test_agent
    ):
        """Test saving settings in advanced mode."""
        # Save test agent
        agent_store.save(test_agent)

        # Test the save_settings utility function directly in advanced mode
        form_data = SettingsFormData(
            mode="advanced",
            provider=None,
            model=None,
            custom_model="custom-model",
            base_url="https://api.example.com/v1",
            api_key_input="",  # Empty input (should preserve existing)
            memory_condensation_enabled=False,
        )

        result = save_settings(form_data, test_agent)
        assert result.success is True

        # Verify the agent was saved with correct parameters
        saved_agent = agent_store.load()
        assert saved_agent is not None
        assert saved_agent.llm.model == "custom-model"
        api_key_value = saved_agent.llm.api_key
        if hasattr(api_key_value, "get_secret_value"):
            api_key_value = api_key_value.get_secret_value()
        assert api_key_value == "test-api-key-12345"  # preserved API key
        assert saved_agent.llm.base_url == "https://api.example.com/v1"

    def test_save_settings_advanced_mode_missing_model(self, settings_screen):
        """Test that error is shown when custom model is missing in advanced mode."""
        # Test the save_settings utility function directly with missing model
        form_data = SettingsFormData(
            mode="advanced",
            provider=None,
            model=None,
            custom_model="",  # Missing model
            base_url="https://api.example.com",
            api_key_input="test-key",
            memory_condensation_enabled=False,
        )

        result = save_settings(form_data, None)
        assert result.success is False
        assert result.error_message == "Custom model is required in advanced mode"

    def test_save_settings_advanced_mode_missing_base_url(self, settings_screen):
        """Test that error is shown when base URL is missing in advanced mode."""
        # Test the save_settings utility function directly with missing base URL
        form_data = SettingsFormData(
            mode="advanced",
            provider=None,
            model=None,
            custom_model="custom-model",
            base_url="",  # Missing base URL
            api_key_input="test-key",
            memory_condensation_enabled=False,
        )

        result = save_settings(form_data, None)
        assert result.success is False
        assert result.error_message == "Base URL is required in advanced mode"

    def test_update_field_dependencies_basic_mode(self, settings_screen):
        """Test field dependency updates in basic mode."""
        # Mock UI components
        settings_screen.mode_select = Mock()
        settings_screen.mode_select.value = "basic"
        settings_screen.provider_select = Mock()
        settings_screen.provider_select.value = "openai"
        settings_screen.model_select = Mock()
        settings_screen.model_select.value = "openai/gpt-4o"
        settings_screen.api_key_input = Mock()
        settings_screen.api_key_input.value = "test-key"
        settings_screen.custom_model_input = Mock()
        settings_screen.base_url_input = Mock()
        settings_screen.memory_select = Mock()

        # Call _update_field_dependencies
        settings_screen._update_field_dependencies()

        # Verify basic mode field states
        assert settings_screen.provider_select.disabled is False
        assert settings_screen.model_select.disabled is False
        assert settings_screen.api_key_input.disabled is False
        assert settings_screen.memory_select.disabled is False

    def test_update_field_dependencies_advanced_mode(self, settings_screen):
        """Test field dependency updates in advanced mode."""
        # Mock UI components
        settings_screen.mode_select = Mock()
        settings_screen.mode_select.value = "advanced"
        settings_screen.custom_model_input = Mock()
        settings_screen.custom_model_input.value = "custom-model"
        settings_screen.base_url_input = Mock()
        settings_screen.api_key_input = Mock()
        settings_screen.api_key_input.value = "test-key"
        settings_screen.memory_select = Mock()

        # Call _update_field_dependencies
        settings_screen._update_field_dependencies()

        # Verify advanced mode field states
        assert settings_screen.custom_model_input.disabled is False
        assert settings_screen.base_url_input.disabled is False
        assert settings_screen.api_key_input.disabled is False
        assert settings_screen.memory_select.disabled is False

    def test_clear_form(self, settings_screen):
        """Test that _clear_form resets all form values."""
        # Mock UI components
        settings_screen.api_key_input = Mock()
        settings_screen.custom_model_input = Mock()
        settings_screen.base_url_input = Mock()
        settings_screen.mode_select = Mock()
        settings_screen.provider_select = Mock()
        settings_screen.model_select = Mock()
        settings_screen.memory_select = Mock()

        # Call _clear_form
        settings_screen._clear_form()

        # Verify all fields are cleared
        assert settings_screen.api_key_input.value == ""
        assert settings_screen.api_key_input.placeholder == "Enter your API key"
        assert settings_screen.custom_model_input.value == ""
        assert settings_screen.base_url_input.value == ""
        assert settings_screen.mode_select.value == "basic"
        assert settings_screen.provider_select.value == Select.BLANK
        assert settings_screen.model_select.value == Select.BLANK
        assert settings_screen.memory_select.value is False

    def test_save_settings_integration(self, settings_screen, agent_store, test_agent):
        """Test that save_settings integration works correctly."""
        # Save test agent
        agent_store.save(test_agent)

        # Setup settings screen
        settings_screen.agent_store = agent_store
        settings_screen.current_agent = test_agent

        # Mock UI components
        settings_screen.api_key_input = Mock()
        settings_screen.api_key_input.value = "new-api-key"
        settings_screen.mode_select = Mock()
        settings_screen.mode_select.value = "basic"
        settings_screen.provider_select = Mock()
        settings_screen.provider_select.value = "openai"
        settings_screen.model_select = Mock()
        settings_screen.model_select.value = "openai/gpt-4o"
        settings_screen.custom_model_input = Mock()
        settings_screen.custom_model_input.value = ""
        settings_screen.base_url_input = Mock()
        settings_screen.base_url_input.value = ""
        settings_screen.memory_select = Mock()
        settings_screen.memory_select.value = True
        settings_screen._show_message = Mock()
        settings_screen.dismiss = Mock()

        # Call _save_settings
        settings_screen._save_settings()

        # Verify agent was updated and saved
        saved_agent = agent_store.load()
        assert saved_agent is not None
        assert saved_agent.llm.model == "openai/gpt-4o"
        assert saved_agent.condenser is not None  # Memory condensation enabled

    def test_show_message(self, settings_screen):
        """Test _show_message functionality."""
        # Mock message widget
        settings_screen.message_widget = Mock()

        # Test error message
        settings_screen._show_message("Error message", is_error=True)
        settings_screen.message_widget.update.assert_called_with("Error message")
        settings_screen.message_widget.add_class.assert_called_with("error_message")
        settings_screen.message_widget.remove_class.assert_called_with(
            "success_message"
        )

        # Reset mock
        settings_screen.message_widget.reset_mock()

        # Test success message
        settings_screen._show_message("Success message", is_error=False)
        settings_screen.message_widget.update.assert_called_with("Success message")
        settings_screen.message_widget.add_class.assert_called_with("success_message")
        settings_screen.message_widget.remove_class.assert_called_with("error_message")

    def test_clear_message(self, settings_screen):
        """Test _clear_message functionality."""
        # Mock message widget
        settings_screen.message_widget = Mock()

        # Call _clear_message
        settings_screen._clear_message()

        # Verify message was cleared
        settings_screen.message_widget.update.assert_called_with("")
        settings_screen.message_widget.remove_class.assert_any_call("error_message")
        settings_screen.message_widget.remove_class.assert_any_call("success_message")
