"""Settings tab component for the settings modal."""

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Input, Label, Select, Static

from openhands_cli.tui.modals.settings.choices import (
    provider_options,
)
from openhands_cli.tui.modals.settings.model_recommendations import (
    render_model_recommendations,
)


class SettingsTab(Container):
    """Settings tab component containing all agent configuration options."""

    def compose(self) -> ComposeResult:
        """Compose the settings tab content."""
        with VerticalScroll(id="settings_form"):
            with Container(id="form_content"):
                # Basic Settings Section
                with Container(classes="form_group"):
                    yield Label("Settings Mode:", classes="form_label")
                    yield Select(
                        [("Basic", "basic"), ("Advanced", "advanced")],
                        value="basic",
                        id="mode_select",
                        classes="form_select",
                        type_to_search=True,
                    )

                # Basic Settings Section (shown in Basic mode)
                with Container(id="basic_section", classes="form_group"):
                    # LLM Provider
                    with Container(classes="form_group"):
                        yield Label("LLM Provider:", classes="form_label")
                        yield Select(
                            provider_options,
                            id="provider_select",
                            classes="form_select",
                            type_to_search=True,
                            # Always enabled after mode selection
                            disabled=False,
                        )

                    # LLM Model
                    with Container(classes="form_group"):
                        yield Label("LLM Model:", classes="form_label")
                        yield Select(
                            [("Select provider first", "")],
                            id="model_select",
                            classes="form_select",
                            type_to_search=True,
                            # Disabled until provider is selected
                            disabled=True,
                        )

                # Advanced Settings Section (shown in Advanced mode)
                with Container(id="advanced_section", classes="form_group"):
                    # Custom Model
                    with Container(classes="form_group"):
                        yield Label("Custom Model:", classes="form_label")
                        yield Input(
                            placeholder=("e.g., gpt-4o-mini, claude-3-sonnet"),
                            id="custom_model_input",
                            classes="form_input",
                            # Disabled until Advanced mode is selected
                            disabled=True,
                        )

                    # Base URL
                    with Container(classes="form_group"):
                        yield Label("Base URL:", classes="form_label")
                        yield Input(
                            placeholder=(
                                "e.g., https://api.openai.com/v1, "
                                "https://api.anthropic.com"
                            ),
                            id="base_url_input",
                            classes="form_input",
                            # Disabled until custom model is entered
                            disabled=True,
                        )

                    # Timeout (seconds)
                    with Container(classes="form_group"):
                        yield Label("LLM Timeout (seconds):", classes="form_label")
                        yield Input(
                            placeholder="10–3600 (optional)",
                            id="timeout_input",
                            classes="form_input",
                            # Enabled when API key is entered
                            disabled=True,
                        )

                    # Max Tokens (optional)
                    with Container(classes="form_group"):
                        yield Label("LLM Max Tokens (optional):", classes="form_label")
                        yield Input(
                            placeholder="e.g., 2000",
                            id="max_tokens_input",
                            classes="form_input",
                            disabled=True,
                        )

                    # Max Size (optional)
                    with Container(classes="form_group"):
                        yield Label(
                            "Condenser Max Size (optional):", classes="form_label"
                        )
                        yield Input(
                            placeholder="e.g., 240",
                            id="max_size_input",
                            classes="form_input",
                            disabled=True,
                        )

                # API Key (shown in both modes)
                with Container(classes="form_group"):
                    yield Label("API Key:", classes="form_label")
                    yield Input(
                        placeholder="Enter your API key",
                        password=True,
                        id="api_key_input",
                        classes="form_input",
                        # Disabled until model is selected (Basic) or
                        # custom model entered (Advanced)
                        disabled=True,
                    )

                # Memory Condensation
                with Container(classes="form_group"):
                    yield Label("Memory Condensation:", classes="form_label")
                    yield Select(
                        [("Enabled", True), ("Disabled", False)],
                        value=False,
                        id="memory_condensation_select",
                        classes="form_select",
                        disabled=True,  # Disabled until API key is entered
                    )
                    yield Static(
                        "Memory condensation helps reduce token usage by "
                        "summarizing old conversation history.",
                        classes="form_help",
                    )

                # Model Recommendations Section
                with Container(classes="form_group"):
                    yield Static("Model Recommendations", classes="form_section_title")
                    yield Static(
                        "Based on OpenHands evaluations using the SWE-bench dataset. "
                        "These models have been verified to work well with OpenHands. "
                        "For more details, see: https://docs.openhands.dev/openhands/usage/llms/llms",
                        classes="form_help",
                    )

                    # Render model recommendations
                    yield from render_model_recommendations()

                # Help Section
                with Container(classes="form_group"):
                    yield Static("Configuration Help", classes="form_section_title")
                    yield Static(
                        "• Basic Mode: Choose from verified LLM providers "
                        "and models\n"
                        "• Advanced Mode: Use custom models with your own "
                        "API endpoints\n"
                        "• API Keys are stored securely and masked in the "
                        "interface\n"
                        "• Changes take effect immediately after saving",
                        classes="form_help",
                    )
