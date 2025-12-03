"""Settings screen for OpenHands CLI using Textual.

This module provides a modern form-based settings interface that overlays
the main UI, allowing users to configure their agent settings including
LLM provider, model, API keys, and advanced options.
"""

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static
from textual.widgets._select import NoSelection

from openhands.sdk import LLM
from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands.sdk.llm import UNVERIFIED_MODELS_EXCLUDING_BEDROCK, VERIFIED_MODELS
from openhands_cli.tui.settings.store import AgentStore
from openhands_cli.utils import (
    get_default_cli_agent,
    get_llm_metadata,
    should_set_litellm_extra_body,
)


class SettingsScreen(ModalScreen):
    """A modal screen for configuring agent settings."""

    BINDINGS: ClassVar = [
        ("escape", "cancel", "Cancel"),
    ]

    CSS_PATH = "settings_screen.tcss"

    def __init__(self, is_initial_setup: bool = False, **kwargs):
        """Initialize the settings screen.

        Args:
            is_initial_setup: True if this is the initial setup for a new user
        """
        super().__init__(**kwargs)
        self.agent_store = AgentStore()
        self.current_agent = None
        self.is_advanced_mode = False
        self.message_widget = None
        self.is_initial_setup = is_initial_setup

    def compose(self) -> ComposeResult:
        """Create the settings form."""
        with Container(id="settings_container"):
            yield Static("Agent Settings", id="settings_title")

            # Message area for errors/success
            self.message_widget = Static("", id="message_area")
            yield self.message_widget

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
                            provider_options = self._get_provider_options()
                            yield Select(
                                provider_options,
                                id="provider_select",
                                classes="form_select",
                                type_to_search=True,
                                disabled=False,  # Always enabled after mode selection
                            )

                        # LLM Model
                        with Container(classes="form_group"):
                            yield Label("LLM Model:", classes="form_label")
                            yield Select(
                                [("Select provider first", "")],
                                id="model_select",
                                classes="form_select",
                                type_to_search=True,
                                disabled=True,  # Disabled until provider is selected
                            )

                    # Advanced Settings Section (shown in Advanced mode)
                    with Container(id="advanced_section", classes="form_group"):
                        # Custom Model
                        with Container(classes="form_group"):
                            yield Label("Custom Model:", classes="form_label")
                            yield Input(
                                placeholder="e.g., gpt-4o-mini, claude-3-sonnet",
                                id="custom_model_input",
                                classes="form_input",
                                # Disabled until Advanced mode is selected
                                disabled=True,
                            )

                        # Base URL
                        with Container(classes="form_group"):
                            yield Label("Base URL:", classes="form_label")
                            yield Input(
                                placeholder="e.g., https://api.openai.com/v1, https://api.anthropic.com",
                                id="base_url_input",
                                classes="form_input",
                                disabled=True,  # Disabled until custom model is entered
                            )

                    # API Key (shown in both modes)
                    with Container(classes="form_group"):
                        yield Label("API Key:", classes="form_label")
                        yield Input(
                            placeholder="Enter your API key",
                            password=True,
                            id="api_key_input",
                            classes="form_input",
                            # Disabled until model is selected (Basic) or custom model
                            # entered (Advanced)
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

                    # Help Section
                    with Container(classes="form_group"):
                        yield Static("Configuration Help", classes="form_section_title")
                        yield Static(
                            "• Basic Mode: Choose from verified LLM providers and "
                            "models\n"
                            "• Advanced Mode: Use custom models with your own API "
                            "endpoints\n"
                            "• API Keys are stored securely and masked in the "
                            "interface\n"
                            "• Changes take effect immediately after saving",
                            classes="form_help",
                        )

            # Buttons
            with Horizontal(id="button_container"):
                yield Button(
                    "Save",
                    variant="primary",
                    id="save_button",
                    classes="settings_button",
                )
                yield Button(
                    "Cancel",
                    variant="default",
                    id="cancel_button",
                    classes="settings_button",
                )

    def on_mount(self) -> None:
        """Initialize the form with current settings."""
        self._load_current_settings()
        self._update_advanced_visibility()
        self._update_field_dependencies()

    def on_show(self) -> None:
        """Reload settings when the screen is shown."""
        self._clear_form()
        self._load_current_settings()
        self._update_advanced_visibility()
        self._update_field_dependencies()

    def _clear_form(self) -> None:
        """Clear all form values before reloading."""
        try:
            # Clear all input fields
            api_key_input = self.query_one("#api_key_input", Input)
            api_key_input.value = ""
            api_key_input.placeholder = "Enter your API key"

            custom_model_input = self.query_one("#custom_model_input", Input)
            custom_model_input.value = ""

            base_url_input = self.query_one("#base_url_input", Input)
            base_url_input.value = ""

            # Reset selects to default values
            mode_select = self.query_one("#mode_select", Select)
            mode_select.value = "basic"

            provider_select = self.query_one("#provider_select", Select)
            provider_select.value = Select.BLANK

            model_select = self.query_one("#model_select", Select)
            model_select.value = Select.BLANK

            memory_select = self.query_one("#memory_condensation_select", Select)
            memory_select.value = False

        except Exception:
            # If any widget is not found, just continue
            pass

    def _get_provider_options(self) -> list[tuple[str, str]]:
        """Get list of available LLM providers."""
        providers = list(VERIFIED_MODELS.keys()) + list(
            UNVERIFIED_MODELS_EXCLUDING_BEDROCK.keys()
        )
        return [(provider, provider) for provider in providers]

    def _get_model_options(self, provider: str) -> list[tuple[str, str]]:
        """Get list of available models for a provider."""
        models = VERIFIED_MODELS.get(
            provider, []
        ) + UNVERIFIED_MODELS_EXCLUDING_BEDROCK.get(provider, [])
        return [(model, model) for model in models]

    def _load_current_settings(self) -> None:
        """Load current agent settings into the form."""
        try:
            # Always reload from store to get latest settings
            self.current_agent = self.agent_store.load()
            if not self.current_agent:
                return

            llm = self.current_agent.llm

            # Determine if we're in advanced mode
            self.is_advanced_mode = bool(llm.base_url)
            mode_select = self.query_one("#mode_select", Select)
            mode_select.value = "advanced" if self.is_advanced_mode else "basic"

            if self.is_advanced_mode:
                # Advanced mode - populate custom model and base URL
                custom_model_input = self.query_one("#custom_model_input", Input)
                custom_model_input.value = llm.model or ""

                base_url_input = self.query_one("#base_url_input", Input)
                base_url_input.value = llm.base_url or ""
            else:
                # Basic mode - populate provider and model selects
                if "/" in llm.model:
                    provider, model = llm.model.split("/", 1)

                    provider_select = self.query_one("#provider_select", Select)
                    provider_select.value = provider

                    # Update model options and select current model
                    self._update_model_options(provider)
                    model_select = self.query_one("#model_select", Select)
                    model_select.value = llm.model

            # API Key (show masked version)
            api_key_input = self.query_one("#api_key_input", Input)
            if llm.api_key:
                # Show masked key as placeholder
                try:
                    key_value = llm.api_key.get_secret_value()  # type: ignore
                except AttributeError:
                    key_value = str(llm.api_key)
                api_key_input.placeholder = f"Current: {key_value[:3]}***"
            else:
                # No API key set
                api_key_input.placeholder = "Enter your API key"

            # Memory Condensation
            memory_select = self.query_one("#memory_condensation_select", Select)
            memory_select.value = bool(self.current_agent.condenser)

            # Update field dependencies after loading all values
            self._update_field_dependencies()

        except Exception as e:
            self._show_message(f"Error loading settings: {str(e)}", is_error=True)

    def _update_model_options(self, provider: str) -> None:
        """Update model select options based on provider."""
        model_select = self.query_one("#model_select", Select)
        model_options = self._get_model_options(provider)

        if model_options:
            model_select.set_options(model_options)
        else:
            model_select.set_options([("No models available", "")])

    def _update_advanced_visibility(self) -> None:
        """Show/hide basic and advanced sections based on mode."""
        basic_section = self.query_one("#basic_section")
        advanced_section = self.query_one("#advanced_section")

        if self.is_advanced_mode:
            basic_section.display = False
            advanced_section.display = True
        else:
            basic_section.display = True
            advanced_section.display = False

    def _update_field_dependencies(self) -> None:
        """Update field enabled/disabled state based on dependency chain."""
        try:
            # Get current values
            mode_select = self.query_one("#mode_select", Select)
            api_key_input = self.query_one("#api_key_input", Input)
            memory_select = self.query_one("#memory_condensation_select", Select)

            mode = mode_select.value if hasattr(mode_select, "value") else None
            api_key = (
                api_key_input.value.strip() if hasattr(api_key_input, "value") else ""
            )

            # Dependency chain logic
            is_basic_mode = mode == "basic"
            is_advanced_mode = mode == "advanced"

            # Basic mode fields
            if is_basic_mode:
                try:
                    provider_select = self.query_one("#provider_select", Select)
                    model_select = self.query_one("#model_select", Select)

                    provider = (
                        provider_select.value
                        if hasattr(provider_select, "value")
                        else None
                    )
                    model = (
                        model_select.value if hasattr(model_select, "value") else None
                    )

                    # Provider is always enabled in basic mode
                    provider_select.disabled = False

                    # Model select: enabled when provider is selected
                    model_select.disabled = not (provider and provider != Select.BLANK)

                    # API Key: enabled when model is selected
                    api_key_input.disabled = not (model and model != Select.BLANK)
                except Exception:
                    pass

            # Advanced mode fields
            elif is_advanced_mode:
                try:
                    custom_model_input = self.query_one("#custom_model_input", Input)
                    base_url_input = self.query_one("#base_url_input", Input)

                    custom_model = (
                        custom_model_input.value.strip()
                        if hasattr(custom_model_input, "value")
                        else ""
                    )

                    # Custom model: always enabled in Advanced mode
                    custom_model_input.disabled = False

                    # Base URL: enabled when custom model is entered
                    base_url_input.disabled = not custom_model

                    # API Key: enabled when custom model is entered
                    api_key_input.disabled = not custom_model
                except Exception:
                    pass

            # Memory Condensation: enabled when API key is provided
            memory_select.disabled = not api_key

        except Exception:
            # Silently handle errors during initialization
            pass

    def _show_message(self, message: str, is_error: bool = False) -> None:
        """Show a message to the user."""
        if self.message_widget:
            self.message_widget.update(message)
            self.message_widget.add_class(
                "error_message" if is_error else "success_message"
            )
            self.message_widget.remove_class(
                "success_message" if is_error else "error_message"
            )

    def _clear_message(self) -> None:
        """Clear the message area."""
        if self.message_widget:
            self.message_widget.update("")
            self.message_widget.remove_class("error_message")
            self.message_widget.remove_class("success_message")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select widget changes."""
        if event.select.id == "mode_select":
            self.is_advanced_mode = event.value == "advanced"
            self._update_advanced_visibility()
            self._update_field_dependencies()
            self._clear_message()
        elif event.select.id == "provider_select":
            if event.value is not NoSelection:
                self._update_model_options(str(event.value))
            self._update_field_dependencies()
            self._clear_message()
        elif event.select.id == "model_select":
            self._update_field_dependencies()
            self._clear_message()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input field changes."""
        if event.input.id in ["custom_model_input", "api_key_input"]:
            self._update_field_dependencies()
            self._clear_message()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save_button":
            self._save_settings()
        elif event.button.id == "cancel_button":
            self._handle_cancel()

    def action_cancel(self) -> None:
        """Handle escape key to cancel settings."""
        self._handle_cancel()

    def _handle_cancel(self) -> None:
        """Handle cancel action - check if this is initial setup."""
        if self.is_initial_setup:
            # Check if there are any existing settings
            existing_agent = self.agent_store.load()
            if existing_agent is None:
                # No existing settings and this is initial setup - return False
                # to trigger exit modal
                self._close_screen(success=False)
                return

        # Normal cancel behavior - just close the screen
        self._close_screen(success=False)

    def _save_settings(self) -> None:
        """Save the current settings."""
        try:
            # Collect form data
            mode_select = self.query_one("#mode_select", Select)
            api_key_input = self.query_one("#api_key_input", Input)
            memory_select = self.query_one("#memory_condensation_select", Select)

            api_key = api_key_input.value.strip()

            # If no API key entered, keep existing one
            if not api_key and self.current_agent and self.current_agent.llm.api_key:
                try:
                    api_key = self.current_agent.llm.api_key.get_secret_value()  # type: ignore
                except AttributeError:
                    api_key = str(self.current_agent.llm.api_key)

            if not api_key:
                self._show_message("API Key is required", is_error=True)
                return

            if mode_select.value == "advanced":
                # Advanced mode
                custom_model_input = self.query_one("#custom_model_input", Input)
                base_url_input = self.query_one("#base_url_input", Input)

                model = custom_model_input.value.strip()
                base_url = base_url_input.value.strip()

                if not model:
                    self._show_message(
                        "Custom model is required in advanced mode", is_error=True
                    )
                    return
                if not base_url:
                    self._show_message(
                        "Base URL is required in advanced mode", is_error=True
                    )
                    return

                self._save_llm_settings(model, api_key, base_url)
            else:
                # Basic mode
                provider_select = self.query_one("#provider_select", Select)
                model_select = self.query_one("#model_select", Select)

                provider = provider_select.value
                model = model_select.value

                if provider is NoSelection or not provider:
                    self._show_message("Please select a provider", is_error=True)
                    return
                if model is NoSelection or not model:
                    self._show_message("Please select a model", is_error=True)
                    return

                model_str = str(model)
                full_model = (
                    f"{provider}/{model_str}" if "/" not in model_str else model_str
                )
                self._save_llm_settings(full_model, api_key)

            # Handle memory condensation
            if memory_select.value is not NoSelection:
                self._update_memory_condensation(memory_select.value == "enabled")

            # Close the screen immediately - no delay needed
            self._close_screen()

        except Exception as e:
            self._show_message(f"Error saving settings: {str(e)}", is_error=True)

    def _close_screen(self, success: bool = True) -> None:
        """Safely close the settings screen and return to the main UI."""
        try:
            # For ModalScreen, we should use dismiss() to properly close
            # Return True if settings were saved successfully
            self.dismiss(success)
        except Exception:
            # Fallback to pop_screen if dismiss fails
            try:
                self.app.pop_screen()
            except Exception:
                # Last resort - just pass, let the app handle it
                pass

    def _save_llm_settings(
        self, model: str, api_key: str, base_url: str | None = None
    ) -> None:
        """Save LLM settings to the agent store."""
        extra_kwargs: dict[str, Any] = {}
        if should_set_litellm_extra_body(model):
            extra_kwargs["litellm_extra_body"] = {
                "metadata": get_llm_metadata(model_name=model, llm_type="agent")
            }

        llm = LLM(
            model=model,
            api_key=api_key,
            base_url=base_url,
            usage_id="agent",
            **extra_kwargs,
        )

        agent = self.current_agent or get_default_cli_agent(llm=llm)
        agent = agent.model_copy(update={"llm": llm})

        # Update condenser LLM as well
        if agent.condenser and isinstance(agent.condenser, LLMSummarizingCondenser):
            condenser_llm = llm.model_copy(update={"usage_id": "condenser"})
            if should_set_litellm_extra_body(model):
                condenser_llm = condenser_llm.model_copy(
                    update={
                        "litellm_extra_body": {
                            "metadata": get_llm_metadata(
                                model_name=model, llm_type="condenser"
                            )
                        }
                    }
                )
            agent = agent.model_copy(
                update={
                    "condenser": agent.condenser.model_copy(
                        update={"llm": condenser_llm}
                    )
                }
            )

        self.agent_store.save(agent)
        self.current_agent = agent

    def _update_memory_condensation(self, enabled: bool) -> None:
        """Update memory condensation setting."""
        if not self.current_agent:
            return

        if enabled and not self.current_agent.condenser:
            # Enable condensation
            condenser_llm = self.current_agent.llm.model_copy(
                update={"usage_id": "condenser"}
            )
            condenser = LLMSummarizingCondenser(llm=condenser_llm)
            self.current_agent = self.current_agent.model_copy(
                update={"condenser": condenser}
            )
        elif not enabled and self.current_agent.condenser:
            # Disable condensation
            self.current_agent = self.current_agent.model_copy(
                update={"condenser": None}
            )

        self.agent_store.save(self.current_agent)
