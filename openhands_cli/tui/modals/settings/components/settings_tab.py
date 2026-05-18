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


class SettingsFormScroll(VerticalScroll, can_focus=False):
    pass


class SettingsTab(Container):
    """Settings tab component containing all agent configuration options."""

    def compose(self) -> ComposeResult:
        """Compose the settings tab content."""
        with SettingsFormScroll(id="settings_form"):
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
                        yield Label(
                            "LLM Max Input Tokens (optional):", classes="form_label"
                        )
                        yield Input(
                            placeholder="e.g., 128000",
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

                # Databricks-only: workspace host + auth method + conditional
                # credential inputs. The whole block is hidden unless the
                # active provider / custom model is Databricks; see
                # ``_update_databricks_visibility`` in settings_screen.py.
                #
                # Note: a separate AI Gateway host override is supported via
                # the DATABRICKS_AI_GATEWAY_HOST environment variable for
                # split-hostname deployments, but is intentionally not
                # surfaced in the UI to keep the form simple.
                with Container(id="databricks_auth_section", classes="form_group"):
                    with Container(classes="form_group"):
                        yield Label(
                            "Databricks Workspace Host:",
                            classes="form_label",
                        )
                        yield Input(
                            placeholder=("https://adb-1234567890.cloud.databricks.com"),
                            id="databricks_host_input",
                            classes="form_input",
                        )
                        yield Static(
                            "Required. Your Databricks workspace URL. Used for "
                            "Foundation Model invocations, OAuth token "
                            "minting, and model discovery.",
                            classes="form_help",
                        )

                    with Container(classes="form_group"):
                        yield Label("Databricks Auth Method:", classes="form_label")
                        yield Select(
                            [
                                ("Personal Access Token (PAT)", "pat"),
                                ("Service Principal (M2M)", "m2m"),
                                ("CLI Profile (~/.databrickscfg)", "profile"),
                                (
                                    "Browser SSO via `databricks auth login` "
                                    "(U2M / unified)",
                                    "u2m",
                                ),
                            ],
                            value="pat",
                            id="databricks_auth_method_select",
                            classes="form_select",
                            type_to_search=False,
                        )
                        yield Static(
                            "PAT: paste a Personal Access Token below.",
                            id="databricks_auth_method_help",
                            classes="form_help",
                        )

                    with Container(id="databricks_profile_group", classes="form_group"):
                        yield Label("Databricks Profile Name:", classes="form_label")
                        yield Input(
                            placeholder="DEFAULT",
                            id="databricks_profile_input",
                            classes="form_input",
                        )

                    with Container(id="databricks_m2m_group", classes="form_group"):
                        yield Label("Databricks Client ID:", classes="form_label")
                        yield Input(
                            placeholder="service-principal client id",
                            id="databricks_client_id_input",
                            classes="form_input",
                        )
                        yield Label("Databricks Client Secret:", classes="form_label")
                        yield Input(
                            placeholder="service-principal client secret",
                            password=True,
                            id="databricks_client_secret_input",
                            classes="form_input",
                        )

                # API Key (shown in both modes; hidden for Databricks non-PAT auth)
                with Container(id="api_key_group", classes="form_group"):
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
                        value=True,
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
