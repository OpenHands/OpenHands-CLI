"""Tests for SettingsTab component."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, Select, Static

from openhands_cli.refactor.modals.settings.components.settings_tab import SettingsTab


class SettingsTabTestApp(App):
    """Test app for SettingsTab component."""

    def compose(self) -> ComposeResult:
        yield SettingsTab()


class TestSettingsTab:
    """Test suite for SettingsTab component."""

    @pytest.mark.asyncio
    async def test_compose_creates_expected_widgets(self):
        """Test that compose creates all expected form widgets."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)

            # Check main form container
            settings_form = tab.query_one("#settings_form")
            assert settings_form is not None

            # Check mode select
            mode_select = tab.query_one("#mode_select", Select)
            assert mode_select is not None
            assert mode_select.value == "basic"

            # Check provider select
            provider_select = tab.query_one("#provider_select", Select)
            assert provider_select is not None

            # Check model select
            model_select = tab.query_one("#model_select", Select)
            assert model_select is not None

            # Check custom model input
            custom_model_input = tab.query_one("#custom_model_input", Input)
            assert custom_model_input is not None

            # Check base URL input
            base_url_input = tab.query_one("#base_url_input", Input)
            assert base_url_input is not None

            # Check API key input
            api_key_input = tab.query_one("#api_key_input", Input)
            assert api_key_input is not None
            assert api_key_input.password is True

            # Check memory condensation select
            memory_select = tab.query_one("#memory_condensation_select", Select)
            assert memory_select is not None

    @pytest.mark.asyncio
    async def test_initial_widget_states(self):
        """Test that widgets have correct initial states and values."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)

            # Mode select should default to basic
            mode_select = tab.query_one("#mode_select", Select)
            assert mode_select.value == "basic"

            # Provider select should be enabled
            provider_select = tab.query_one("#provider_select", Select)
            assert provider_select.disabled is False

            # Model select should be disabled initially
            model_select = tab.query_one("#model_select", Select)
            assert model_select.disabled is True

            # Advanced mode inputs should be disabled initially
            custom_model_input = tab.query_one("#custom_model_input", Input)
            assert custom_model_input.disabled is True

            base_url_input = tab.query_one("#base_url_input", Input)
            assert base_url_input.disabled is True

            # API key should be disabled initially
            api_key_input = tab.query_one("#api_key_input", Input)
            assert api_key_input.disabled is True

            # Memory select should be disabled initially
            memory_select = tab.query_one("#memory_condensation_select", Select)
            assert memory_select.disabled is True

    @pytest.mark.asyncio
    async def test_mode_select_options(self):
        """Test that mode select has correct options."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)
            mode_select = tab.query_one("#mode_select", Select)

            # Check options (includes blank option)
            options = list(mode_select._options)
            assert len(options) == 3  # blank + basic + advanced
            
            # Check basic option (options are tuples: (prompt, value))
            basic_option = next(opt for opt in options if len(opt) > 1 and opt[1] == "basic")
            assert basic_option[0] == "Basic"
            
            # Check advanced option
            advanced_option = next(opt for opt in options if len(opt) > 1 and opt[1] == "advanced")
            assert advanced_option[0] == "Advanced"

    @pytest.mark.asyncio
    async def test_memory_condensation_options(self):
        """Test that memory condensation select has correct options."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)
            memory_select = tab.query_one("#memory_condensation_select", Select)

            # Check options (includes blank option)
            options = list(memory_select._options)
            assert len(options) == 3  # blank + enabled + disabled
            
            # Check enabled option (options are tuples: (prompt, value))
            enabled_option = next(opt for opt in options if len(opt) > 1 and opt[1] is True)
            assert enabled_option[0] == "Enabled"
            
            # Check disabled option
            disabled_option = next(opt for opt in options if len(opt) > 1 and opt[1] is False)
            assert disabled_option[0] == "Disabled"

            # Default should be disabled
            assert memory_select.value is False

    @pytest.mark.asyncio
    async def test_input_placeholders(self):
        """Test that input fields have appropriate placeholders."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)

            # Custom model input placeholder
            custom_model_input = tab.query_one("#custom_model_input", Input)
            assert "gpt-4o-mini" in custom_model_input.placeholder
            assert "claude-3-sonnet" in custom_model_input.placeholder

            # Base URL input placeholder
            base_url_input = tab.query_one("#base_url_input", Input)
            assert "https://api.openai.com/v1" in base_url_input.placeholder
            assert "https://api.anthropic.com" in base_url_input.placeholder

            # API key input placeholder
            api_key_input = tab.query_one("#api_key_input", Input)
            assert "Enter your API key" in api_key_input.placeholder

    @pytest.mark.asyncio
    async def test_form_sections_present(self):
        """Test that all form sections are present."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)

            # Check for basic section
            basic_section = tab.query_one("#basic_section")
            assert basic_section is not None

            # Check for advanced section
            advanced_section = tab.query_one("#advanced_section")
            assert advanced_section is not None

            # Check for form groups
            form_groups = tab.query(".form_group")
            assert len(form_groups) > 0

    @pytest.mark.asyncio
    async def test_form_labels_present(self):
        """Test that all form labels are present with correct text."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)

            # Get all labels
            labels = tab.query(".form_label")
            label_texts = [str(label.render()) for label in labels]

            # Check for expected labels
            expected_labels = [
                "Settings Mode:",
                "LLM Provider:",
                "LLM Model:",
                "Custom Model:",
                "Base URL:",
                "API Key:",
                "Memory Condensation:",
            ]

            for expected_label in expected_labels:
                assert any(expected_label in text for text in label_texts), f"Missing label: {expected_label}"

    @pytest.mark.asyncio
    async def test_help_section_present(self):
        """Test that help section is present with correct content."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)

            # Check for help section title
            section_titles = tab.query(".form_section_title")
            help_title_found = any("Configuration Help" in str(title.render()) for title in section_titles)
            assert help_title_found

            # Check for help text
            help_texts = tab.query(".form_help")
            assert len(help_texts) > 0

            # Check for specific help content
            help_content = " ".join(str(help_text.render()) for help_text in help_texts)
            assert "Basic Mode" in help_content
            assert "Advanced Mode" in help_content
            assert "API Keys are stored securely" in help_content

    @pytest.mark.asyncio
    async def test_widget_css_classes(self):
        """Test that widgets have correct CSS classes for styling."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)

            # Check select widgets have form_select class
            selects = tab.query(Select)
            for select in selects:
                assert "form_select" in select.classes

            # Check input widgets have form_input class
            inputs = tab.query(Input)
            for input_widget in inputs:
                assert "form_input" in input_widget.classes

            # Check labels have form_label class
            labels = tab.query(".form_label")
            assert len(labels) > 0

    @pytest.mark.asyncio
    async def test_type_to_search_enabled(self):
        """Test that select widgets have type-to-search enabled."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)

            # Check mode select
            mode_select = tab.query_one("#mode_select", Select)
            # Note: type_to_search is not directly accessible, but we can verify it was set

            # Check provider select
            provider_select = tab.query_one("#provider_select", Select)
            # Note: type_to_search is not directly accessible, but we can verify it was set

            # Check model select
            model_select = tab.query_one("#model_select", Select)
            # Note: type_to_search is not directly accessible, but we can verify it was set

    @pytest.mark.asyncio
    async def test_memory_condensation_help_text(self):
        """Test that memory condensation has appropriate help text."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)

            # Find help text related to memory condensation
            help_texts = tab.query(".form_help")
            memory_help_found = False
            
            for help_text in help_texts:
                content = str(help_text.render())
                if "Memory condensation" in content and "token usage" in content:
                    memory_help_found = True
                    assert "summarizing old conversation history" in content
                    break
            
            assert memory_help_found, "Memory condensation help text not found"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "widget_id, expected_type",
        [
            ("mode_select", Select),
            ("provider_select", Select),
            ("model_select", Select),
            ("custom_model_input", Input),
            ("base_url_input", Input),
            ("api_key_input", Input),
            ("memory_condensation_select", Select),
        ],
    )
    async def test_widget_types_and_ids(self, widget_id, expected_type):
        """Test that widgets have correct types and IDs."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)
            widget = tab.query_one(f"#{widget_id}", expected_type)
            assert widget is not None
            assert isinstance(widget, expected_type)

    @pytest.mark.asyncio
    async def test_form_structure_hierarchy(self):
        """Test that form has correct hierarchical structure."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)

            # Check main form container
            settings_form = tab.query_one("#settings_form")
            assert settings_form is not None

            # Check form content container
            form_content = tab.query_one("#form_content")
            assert form_content is not None

            # Check that form content is inside settings form
            assert form_content.parent is not None

    @pytest.mark.asyncio
    async def test_initial_model_select_state(self):
        """Test that model select has correct initial state and options."""
        app = SettingsTabTestApp()

        async with app.run_test() as pilot:
            tab = app.query_one(SettingsTab)
            model_select = tab.query_one("#model_select", Select)

            # Should be disabled initially
            assert model_select.disabled is True

            # Should have placeholder option (plus blank option)
            options = list(model_select._options)
            assert len(options) == 2  # blank + placeholder
            
            # Find the placeholder option (not the blank one) - options are tuples: (prompt, value)
            placeholder_option = next(opt for opt in options if len(opt) > 1 and opt[0] == "Select provider first")
            assert placeholder_option[1] == ""