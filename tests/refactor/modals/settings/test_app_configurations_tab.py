"""Tests for AppConfigurationsTab component."""

from unittest.mock import patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Switch

from openhands_cli.refactor.modals.settings.app_config import AppConfiguration
from openhands_cli.refactor.modals.settings.components.app_configurations_tab import (
    AppConfigurationsTab,
)


class AppConfigTabTestApp(App):
    """Test app for AppConfigurationsTab component."""

    def __init__(self, initial_config: AppConfiguration | None = None):
        super().__init__()
        self.initial_config = initial_config

    def compose(self) -> ComposeResult:
        if self.initial_config:
            with patch.object(
                AppConfiguration, "load", return_value=self.initial_config
            ):
                yield AppConfigurationsTab()
        else:
            yield AppConfigurationsTab()


class TestAppConfigurationsTab:
    """Test suite for AppConfigurationsTab component."""

    @pytest.mark.parametrize(
        "display_cost_per_action",
        [True, False],
    )
    def test_initialization_with_config(self, display_cost_per_action):
        """Test that tab initializes with correct configuration values."""
        config = AppConfiguration(display_cost_per_action=display_cost_per_action)

        with patch.object(AppConfiguration, "load", return_value=config):
            tab = AppConfigurationsTab()

        assert tab.app_config.display_cost_per_action == display_cost_per_action

    def test_initialization_loads_config(self):
        """Test that tab loads configuration on initialization."""
        with patch.object(AppConfiguration, "load") as mock_load:
            mock_config = AppConfiguration(display_cost_per_action=True)
            mock_load.return_value = mock_config

            tab = AppConfigurationsTab()

            mock_load.assert_called_once()
            assert tab.app_config == mock_config

    @pytest.mark.asyncio
    async def test_compose_creates_expected_widgets(self):
        """Test that compose creates all expected widgets with correct structure."""
        config = AppConfiguration(display_cost_per_action=False)
        app = AppConfigTabTestApp(initial_config=config)

        async with app.run_test():
            tab = app.query_one(AppConfigurationsTab)

            # Check that main container exists
            app_config_content = tab.query_one("#app_config_content")
            assert app_config_content is not None

            # Check that switch exists with correct ID
            display_cost_switch = tab.query_one("#display_cost_switch", Switch)
            assert display_cost_switch is not None
            assert display_cost_switch.value == config.display_cost_per_action

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "initial_value, expected_value",
        [
            (True, True),
            (False, False),
        ],
    )
    async def test_switch_reflects_initial_config(self, initial_value, expected_value):
        """Test that switch widget reflects initial configuration value."""
        config = AppConfiguration(display_cost_per_action=initial_value)
        app = AppConfigTabTestApp(initial_config=config)

        async with app.run_test():
            tab = app.query_one(AppConfigurationsTab)
            switch = tab.query_one("#display_cost_switch", Switch)

            assert switch.value == expected_value

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "switch_value, expected_config_value",
        [
            (True, True),
            (False, False),
        ],
    )
    async def test_get_app_config_returns_current_form_values(
        self, switch_value, expected_config_value
    ):
        """Test that get_app_config returns configuration based on current form
        values."""
        # Start with opposite value to ensure we're testing form state,
        # not initial state
        initial_config = AppConfiguration(display_cost_per_action=not switch_value)
        app = AppConfigTabTestApp(initial_config=initial_config)

        async with app.run_test():
            tab = app.query_one(AppConfigurationsTab)
            switch = tab.query_one("#display_cost_switch", Switch)

            # Set switch to desired value
            switch.value = switch_value

            # Get config from form
            result_config = tab.get_app_config()

            assert isinstance(result_config, AppConfiguration)
            assert result_config.display_cost_per_action == expected_config_value

    @pytest.mark.asyncio
    async def test_get_app_config_creates_new_instance(self):
        """Test that get_app_config creates a new AppConfiguration instance."""
        config = AppConfiguration(display_cost_per_action=True)
        app = AppConfigTabTestApp(initial_config=config)

        async with app.run_test():
            tab = app.query_one(AppConfigurationsTab)

            result_config = tab.get_app_config()

            # Should be a new instance, not the same object
            assert result_config is not tab.app_config
            assert isinstance(result_config, AppConfiguration)

    @pytest.mark.asyncio
    async def test_widget_classes_and_ids(self):
        """Test that widgets have correct CSS classes and IDs for styling."""
        config = AppConfiguration(display_cost_per_action=False)
        app = AppConfigTabTestApp(initial_config=config)

        async with app.run_test():
            tab = app.query_one(AppConfigurationsTab)

            # Check main content container
            content = tab.query_one("#app_config_content")
            assert content is not None

            # Check switch container and classes
            switch = tab.query_one("#display_cost_switch", Switch)
            assert switch is not None
            assert "form_switch" in switch.classes

            # Check for form groups and labels
            form_groups = tab.query(".form_group")
            assert len(form_groups) > 0

            form_labels = tab.query(".form_label")
            assert len(form_labels) > 0

    def test_app_config_property_caching(self):
        """Test that app_config property doesn't reload unnecessarily."""
        with patch.object(AppConfiguration, "load") as mock_load:
            mock_config = AppConfiguration(display_cost_per_action=True)
            mock_load.return_value = mock_config

            tab = AppConfigurationsTab()

            # Access app_config multiple times
            config1 = tab.app_config
            config2 = tab.app_config
            config3 = tab.app_config

            # Should only load once during initialization
            mock_load.assert_called_once()
            assert config1 is config2 is config3

    @pytest.mark.asyncio
    async def test_switch_interaction(self):
        """Test that switch can be toggled and maintains state."""
        config = AppConfiguration(display_cost_per_action=False)
        app = AppConfigTabTestApp(initial_config=config)

        async with app.run_test() as pilot:
            tab = app.query_one(AppConfigurationsTab)
            switch = tab.query_one("#display_cost_switch", Switch)

            # Initial state
            assert switch.value is False

            # Toggle switch
            await pilot.click(switch)
            assert switch.value is True

            # Toggle again
            await pilot.click(switch)
            assert switch.value is False

    @pytest.mark.asyncio
    async def test_form_help_text_present(self):
        """Test that help text is present for configuration options."""
        config = AppConfiguration(display_cost_per_action=False)
        app = AppConfigTabTestApp(initial_config=config)

        async with app.run_test():
            tab = app.query_one(AppConfigurationsTab)

            # Check for help text elements
            help_elements = tab.query(".form_help")
            assert len(help_elements) > 0

            # Check for switch help specifically
            switch_help = tab.query(".switch_help")
            assert len(switch_help) > 0

    @pytest.mark.asyncio
    async def test_section_title_present(self):
        """Test that section title is present and correctly styled."""
        config = AppConfiguration(display_cost_per_action=False)
        app = AppConfigTabTestApp(initial_config=config)

        async with app.run_test():
            tab = app.query_one(AppConfigurationsTab)

            # Check for section title
            section_titles = tab.query(".form_section_title")
            assert len(section_titles) > 0

            # Verify title content
            title_text = str(section_titles[0].render())
            assert "App Configurations" in title_text

    def test_initialization_handles_load_error(self):
        """Test that initialization handles AppConfiguration.load() errors
        gracefully."""
        with patch.object(
            AppConfiguration, "load", side_effect=Exception("Load failed")
        ):
            # Should not raise exception, should use default config
            with pytest.raises(Exception, match="Load failed"):
                AppConfigurationsTab()

    @pytest.mark.asyncio
    async def test_get_app_config_handles_missing_switch(self):
        """Test that get_app_config handles case where switch widget is missing."""
        config = AppConfiguration(display_cost_per_action=False)
        app = AppConfigTabTestApp(initial_config=config)

        async with app.run_test():
            tab = app.query_one(AppConfigurationsTab)

            # Mock query_one to simulate missing switch
            with patch.object(
                tab, "query_one", side_effect=Exception("Widget not found")
            ):
                with pytest.raises(Exception, match="Widget not found"):
                    tab.get_app_config()

    @pytest.mark.parametrize(
        "config_values",
        [
            {"display_cost_per_action": True},
            {"display_cost_per_action": False},
        ],
    )
    def test_multiple_instances_independent(self, config_values):
        """Test that multiple AppConfigurationsTab instances are independent."""
        config = AppConfiguration(**config_values)

        with patch.object(AppConfiguration, "load", return_value=config):
            tab1 = AppConfigurationsTab()
            tab2 = AppConfigurationsTab()

        # Should be separate instances
        assert tab1 is not tab2
        assert (
            tab1.app_config.display_cost_per_action
            == config_values["display_cost_per_action"]
        )
        assert (
            tab2.app_config.display_cost_per_action
            == config_values["display_cost_per_action"]
        )

        # But configs should be equal in value
        assert (
            tab1.app_config.display_cost_per_action
            == tab2.app_config.display_cost_per_action
        )
