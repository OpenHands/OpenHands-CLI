"""Settings screen for OpenHands CLI using Textual.

This module provides a modern form-based settings interface that overlays
the main UI, allowing users to configure their settings including
LLM provider, model, API keys, and advanced options.
"""

import asyncio
from collections.abc import Callable
from typing import ClassVar, Literal, cast

from textual import getters
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets._select import NoSelection

from openhands.sdk.llm import OpenAISubscriptionAuth
from openhands_cli.stores import AgentStore
from openhands_cli.tui.modals.settings.choices import (
    get_model_options,
    is_chatgpt_provider,
)
from openhands_cli.tui.modals.settings.components import (
    CliSettingsTab,
    SettingsTab,
)
from openhands_cli.tui.modals.settings.utils import SettingsFormData, save_settings


class SettingsScreen(ModalScreen):
    """A modal screen for configuring settings."""

    BINDINGS: ClassVar = [
        ("escape", "cancel", "Cancel"),
    ]

    CSS_PATH = "settings_screen.tcss"

    mode_select: getters.query_one[Select] = getters.query_one("#mode_select")
    provider_select: getters.query_one[Select] = getters.query_one("#provider_select")
    model_select: getters.query_one[Select] = getters.query_one("#model_select")
    custom_model_input: getters.query_one[Input] = getters.query_one(
        "#custom_model_input"
    )
    base_url_input: getters.query_one[Input] = getters.query_one("#base_url_input")
    api_key_input: getters.query_one[Input] = getters.query_one("#api_key_input")
    memory_select: getters.query_one[Select] = getters.query_one(
        "#memory_condensation_select"
    )
    basic_section: getters.query_one[Container] = getters.query_one("#basic_section")
    advanced_section: getters.query_one[Container] = getters.query_one(
        "#advanced_section"
    )
    api_key_section: getters.query_one[Container] = getters.query_one(
        "#api_key_section"
    )
    chatgpt_auth_section: getters.query_one[Container] = getters.query_one(
        "#chatgpt_auth_section"
    )
    chatgpt_auth_status: getters.query_one[Static] = getters.query_one(
        "#chatgpt_auth_status"
    )
    chatgpt_login_button: getters.query_one[Button] = getters.query_one(
        "#chatgpt_login_button"
    )
    chatgpt_copy_url_button: getters.query_one[Button] = getters.query_one(
        "#chatgpt_copy_url_button"
    )

    def __init__(
        self,
        on_settings_saved: Callable[[], None] | list[Callable[[], None]] | None = None,
        on_first_time_settings_cancelled: Callable[[], None] | None = None,
        env_overrides_enabled: bool = False,
        **kwargs,
    ):
        """Initialize the settings screen.

        Args:
            on_settings_saved: Callback(s) to invoke when settings are saved
            on_first_time_settings_cancelled: Callback to invoke when settings are
                cancelled during first-time setup
            env_overrides_enabled: If True, environment variables will override
                stored LLM settings when checking for initial setup
        """
        super().__init__(**kwargs)
        self.agent_store = AgentStore()
        self.current_agent = self.agent_store.load_from_disk()
        self.is_advanced_mode = False
        self.message_widget = None
        self.is_initial_setup = SettingsScreen.is_initial_setup_required(
            env_overrides_enabled=env_overrides_enabled
        )

        # ChatGPT subscription auth state
        self._chatgpt_auth = OpenAISubscriptionAuth()
        self._chatgpt_authenticated = False
        self._chatgpt_login_task: asyncio.Task | None = None

        # Convert single callback to list for uniform handling
        if on_settings_saved is None:
            self.on_settings_saved = []
        elif callable(on_settings_saved):
            self.on_settings_saved = [on_settings_saved]
        else:
            self.on_settings_saved = on_settings_saved

        self.on_first_time_settings_cancelled = on_first_time_settings_cancelled

    def compose(self) -> ComposeResult:
        """Create the settings form with tabs."""
        with Container(id="settings_container"):
            yield Static("Settings", id="settings_title")

            # Message area for errors/success
            self.message_widget = Static("", id="message_area")
            yield self.message_widget

            # Tabbed content
            with TabbedContent(id="settings_tabs"):
                # Settings Tab
                with TabPane("Agent Settings", id="settings_tab"):
                    yield SettingsTab()

                # CLI Settings Tab - only show if not first-time setup
                if not self.is_initial_setup:
                    with TabPane("CLI Settings", id="cli_settings_tab"):
                        yield CliSettingsTab()

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
        self._update_chatgpt_auth_visibility()
        self._update_field_dependencies()
        self._check_existing_chatgpt_credentials()

    def on_show(self) -> None:
        """Reload settings when the screen is shown."""
        # Only reload if we don't have current settings loaded
        # This prevents unnecessary clearing when returning from modals
        if not self.current_agent:
            self._clear_form()
            self._load_current_settings()
            self._update_advanced_visibility()
            self._update_chatgpt_auth_visibility()
            self._update_field_dependencies()

    def _clear_form(self) -> None:
        """Clear all form values before reloading."""
        self.api_key_input.value = ""
        self.api_key_input.placeholder = "Enter your API key"

        self.custom_model_input.value = ""
        self.base_url_input.value = ""
        self.mode_select.value = "basic"
        self.provider_select.value = Select.BLANK
        self.model_select.value = Select.BLANK
        self.memory_select.value = False

        # Reset ChatGPT auth state
        self._chatgpt_authenticated = False
        self._update_chatgpt_auth_status()

    def _load_current_settings(self) -> None:
        """Load current settings into the form."""
        if not self.current_agent:
            return

        llm = self.current_agent.llm

        # Determine if we're in advanced mode
        self.is_advanced_mode = bool(llm.base_url)
        self.mode_select.value = "advanced" if self.is_advanced_mode else "basic"

        if self.is_advanced_mode:
            # Advanced mode - populate custom model and base URL
            self.custom_model_input.value = llm.model or ""
            self.base_url_input.value = llm.base_url or ""
        else:
            # Basic mode - populate provider and model selects
            if "/" in llm.model:
                provider, model = llm.model.split("/", 1)
                self.provider_select.value = provider

                # Update model options and select current model
                self._update_model_options(provider)
                # Use model without provider prefix (dropdown options don't have it)
                self.model_select.value = model

        # API Key (show masked version)
        if llm.api_key:
            key_value = (
                llm.api_key
                if isinstance(llm.api_key, str)
                else llm.api_key.get_secret_value()
            )
            self.api_key_input.placeholder = (
                f"Current: {key_value[:3]}*** (leave empty to keep current)"
            )
        else:
            # No API key set
            self.api_key_input.placeholder = "Enter your API key"

        # Memory Condensation
        self.memory_select.value = bool(self.current_agent.condenser)

        # Update field dependencies after loading all values
        self._update_field_dependencies()

    def _update_model_options(self, provider: str) -> None:
        """Update model select options based on provider."""
        # Store current selection to preserve it if possible
        current_selection = self.model_select.value

        model_options = get_model_options(provider)

        if model_options:
            self.model_select.set_options(model_options)

            # Try to preserve the current selection if it's still valid
            if current_selection and current_selection != Select.BLANK:
                # Check if the current selection is still in the new options
                option_values = [option[1] for option in model_options]
                if current_selection in option_values:
                    self.model_select.value = current_selection
        else:
            self.model_select.set_options([("No models available", "")])

    def _update_advanced_visibility(self) -> None:
        """Show/hide basic and advanced sections based on mode."""
        if self.is_advanced_mode:
            self.basic_section.display = False
            self.advanced_section.display = True
        else:
            self.basic_section.display = True
            self.advanced_section.display = False

    def _has_existing_api_key(self) -> bool:
        """Check if there's an existing API key in the agent."""
        return bool(
            self.current_agent
            and self.current_agent.llm
            and self.current_agent.llm.api_key
        )

    def _update_chatgpt_auth_visibility(self) -> None:
        """Show/hide ChatGPT auth section based on selected provider."""
        try:
            provider = self.provider_select.value
            is_chatgpt = is_chatgpt_provider(str(provider) if provider else None)

            # Show ChatGPT auth section only when ChatGPT provider is selected
            # and we're in basic mode
            show_chatgpt = is_chatgpt and not self.is_advanced_mode
            self.chatgpt_auth_section.display = show_chatgpt
            self.api_key_section.display = not show_chatgpt
        except Exception:
            # During initialization, widgets may not be ready
            pass

    def _check_existing_chatgpt_credentials(self) -> None:
        """Check if there are existing valid ChatGPT credentials."""
        try:
            creds = self._chatgpt_auth.get_credentials()
            if creds is not None:
                self._chatgpt_authenticated = True
                self._update_chatgpt_auth_status()
        except Exception:
            pass

    def _update_chatgpt_auth_status(self) -> None:
        """Update the ChatGPT auth status display."""
        try:
            if self._chatgpt_authenticated:
                self.chatgpt_auth_status.update("✓ Signed in successfully")
                self.chatgpt_auth_status.add_class("success_message")
                self.chatgpt_auth_status.remove_class("error_message")
                self.chatgpt_login_button.label = "Re-authenticate"
            else:
                self.chatgpt_auth_status.update("")
                self.chatgpt_auth_status.remove_class("success_message")
                self.chatgpt_auth_status.remove_class("error_message")
                self.chatgpt_login_button.label = "Sign In with Browser"
        except Exception:
            pass

    async def _perform_chatgpt_login(self) -> None:
        """Perform ChatGPT OAuth login flow."""
        try:
            # Update UI to show waiting state
            self.chatgpt_auth_status.update("⏳ Waiting for browser authentication...")
            self.chatgpt_auth_status.remove_class("success_message")
            self.chatgpt_auth_status.remove_class("error_message")
            self.chatgpt_login_button.disabled = True
            self.chatgpt_login_button.label = "Waiting..."

            # Perform login (opens browser)
            creds = await self._chatgpt_auth.login(open_browser=True)

            if creds is not None:
                self._chatgpt_authenticated = True
                self._update_chatgpt_auth_status()
                self._update_field_dependencies()
            else:
                self.chatgpt_auth_status.update("✗ Authentication failed")
                self.chatgpt_auth_status.add_class("error_message")
                self.chatgpt_login_button.label = "Try Again"

        except Exception as e:
            self.chatgpt_auth_status.update(f"✗ Error: {e}")
            self.chatgpt_auth_status.add_class("error_message")
            self.chatgpt_login_button.label = "Try Again"
        finally:
            self.chatgpt_login_button.disabled = False

    async def _copy_chatgpt_auth_url(self) -> None:
        """Copy ChatGPT OAuth URL to clipboard and start waiting for callback."""
        import webbrowser

        import pyperclip

        captured_url: str | None = None

        # Temporarily patch webbrowser.open to capture URL and copy to clipboard
        original_open = webbrowser.open

        def capture_and_copy_url(url: str, *_args, **_kwargs) -> bool:
            nonlocal captured_url
            captured_url = url
            # Copy immediately using pyperclip (same as app's clipboard)
            try:
                pyperclip.copy(url)
            except pyperclip.PyperclipException:
                pass
            # Also use OSC 52 fallback
            self.app.copy_to_clipboard(url)
            # Update status now that URL is copied
            self.chatgpt_auth_status.update(
                "📋 URL copied! Paste in browser, waiting for auth..."
            )
            return True  # Pretend we opened it

        try:
            # Update UI
            self.chatgpt_auth_status.update("📋 Copying auth URL...")
            self.chatgpt_copy_url_button.disabled = True
            self.chatgpt_login_button.disabled = True

            # Patch webbrowser.open to capture URL
            webbrowser.open = capture_and_copy_url

            # Start login flow (won't actually open browser due to patch)
            creds = await self._chatgpt_auth.login(open_browser=True)

            if creds is not None:
                self._chatgpt_authenticated = True
                self._update_chatgpt_auth_status()
                self._update_field_dependencies()
            else:
                self.chatgpt_auth_status.update("✗ Authentication failed")
                self.chatgpt_auth_status.add_class("error_message")

        except Exception as e:
            self.chatgpt_auth_status.update(f"✗ Error: {e}")
            self.chatgpt_auth_status.add_class("error_message")
        finally:
            # Restore original webbrowser.open
            webbrowser.open = original_open
            self.chatgpt_copy_url_button.disabled = False
            self.chatgpt_login_button.disabled = False

    def _update_field_dependencies(self) -> None:
        """Update field enabled/disabled state based on dependency chain."""
        try:
            mode = (
                self.mode_select.value if hasattr(self.mode_select, "value") else None
            )
            api_key = (
                self.api_key_input.value.strip()
                if hasattr(self.api_key_input, "value")
                else ""
            )

            # Dependency chain logic
            is_basic_mode = mode == "basic"
            is_advanced_mode = mode == "advanced"

            # Basic mode fields
            if is_basic_mode:
                try:
                    provider = (
                        self.provider_select.value
                        if hasattr(self.provider_select, "value")
                        else None
                    )
                    model = (
                        self.model_select.value
                        if hasattr(self.model_select, "value")
                        else None
                    )

                    # Provider is always enabled in basic mode
                    self.provider_select.disabled = False

                    # Model select: enabled when provider is selected
                    self.model_select.disabled = not (
                        provider and provider != Select.BLANK
                    )

                    # Check if ChatGPT provider is selected
                    is_chatgpt = is_chatgpt_provider(
                        str(provider) if provider else None
                    )

                    if is_chatgpt:
                        # For ChatGPT, API key is not needed - auth is via OAuth
                        # Memory is enabled when authenticated
                        self.memory_select.disabled = not self._chatgpt_authenticated
                    else:
                        # API Key: enabled when model is selected
                        self.api_key_input.disabled = not (
                            model and model != Select.BLANK
                        )
                        # Memory Condensation: enabled when API key is provided
                        # or when there's an existing API key in the agent
                        self.memory_select.disabled = not (
                            api_key or self._has_existing_api_key()
                        )
                except Exception:
                    pass

            # Advanced mode fields
            elif is_advanced_mode:
                try:
                    custom_model = (
                        self.custom_model_input.value.strip()
                        if hasattr(self.custom_model_input, "value")
                        else ""
                    )

                    # Custom model: always enabled in Advanced mode
                    self.custom_model_input.disabled = False

                    # Base URL: enabled when custom model is entered
                    self.base_url_input.disabled = not custom_model

                    # API Key: enabled when custom model is entered
                    self.api_key_input.disabled = not custom_model

                    # Memory Condensation: enabled when API key is provided
                    # or when there's an existing API key in the agent
                    self.memory_select.disabled = not (
                        api_key or self._has_existing_api_key()
                    )
                except Exception:
                    pass

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
            self._update_chatgpt_auth_visibility()
            self._update_field_dependencies()
            self._clear_message()
        elif event.select.id == "provider_select":
            if event.value is not NoSelection:
                self._update_model_options(str(event.value))
            self._update_chatgpt_auth_visibility()
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
        elif event.button.id == "chatgpt_login_button":
            # Start async login task
            self._chatgpt_login_task = asyncio.create_task(
                self._perform_chatgpt_login()
            )
        elif event.button.id == "chatgpt_copy_url_button":
            # Start async copy URL task
            self._chatgpt_login_task = asyncio.create_task(
                self._copy_chatgpt_auth_url()
            )

    def action_cancel(self) -> None:
        """Handle escape key to cancel settings."""
        self._handle_cancel()

    def _handle_cancel(self) -> None:
        """Handle cancel action - delegate to appropriate callback."""
        self.dismiss(False)

        if self.on_first_time_settings_cancelled and self.is_initial_setup:
            self.on_first_time_settings_cancelled()

    def _save_settings(self) -> None:
        """Save the current settings."""

        raw_mode = self.mode_select.value

        if raw_mode not in ("basic", "advanced"):
            self._show_message("Please select a settings mode", is_error=True)
            return

        mode = cast(Literal["basic", "advanced"], raw_mode)

        provider_value = self.provider_select.value
        model = self.model_select.value
        custom_model = self.custom_model_input.value
        base_url = self.base_url_input.value

        # Check if ChatGPT provider is selected
        is_chatgpt = is_chatgpt_provider(
            str(provider_value) if provider_value else None
        )

        # Validate ChatGPT auth if ChatGPT provider is selected
        if is_chatgpt and not self._chatgpt_authenticated:
            self._show_message("Please sign in with ChatGPT first", is_error=True)
            return

        form_data = SettingsFormData(
            mode=mode,
            provider=None if provider_value is Select.BLANK else str(provider_value),
            model=None if model is Select.BLANK else str(model),
            custom_model=None if custom_model is Select.BLANK else str(custom_model),
            base_url=None if base_url is Select.BLANK else str(base_url),
            api_key_input=self.api_key_input.value,
            memory_condensation_enabled=bool(self.memory_select.value),
            is_chatgpt_subscription=is_chatgpt,
        )

        result = save_settings(form_data, self.current_agent, self._chatgpt_auth)
        if not result.success:
            self._show_message(result.error_message or "Unknown error", is_error=True)
            return

        # Save CLI settings if not in initial setup mode
        if not self.is_initial_setup:
            try:
                cli_settings_tab = self.query_one("#cli_settings_tab", TabPane)
                cli_settings_component = cli_settings_tab.query_one(CliSettingsTab)
                cli_settings = cli_settings_component.get_cli_settings()

                cli_settings.save()
            except Exception as e:
                self._show_message(
                    f"Settings saved, but CLI settings failed: {str(e)}", is_error=True
                )
                return

        message = (
            "Settings saved successfully! Welcome to OpenHands CLI!"
            if self.is_initial_setup
            else "Settings saved successfully!"
        )
        self._show_message(message, is_error=False)
        # Invoke all callbacks if provided, then close screen
        for callback in self.on_settings_saved:
            try:
                callback()
            except Exception as e:
                self.notify(
                    f"Error occurred when saving settings: {e}", severity="error"
                )
        self.dismiss(True)

    @staticmethod
    def is_initial_setup_required(env_overrides_enabled: bool = False) -> bool:
        """Check if initial setup is required.

        Args:
            env_overrides_enabled: If True, environment variables will override
                stored LLM settings.

        Returns:
            True if initial setup is needed (no existing settings and no valid
            env overrides), False otherwise.

        Raises:
            MissingEnvironmentVariablesError: If env_overrides_enabled is True
                but required environment variables (LLM_API_KEY, LLM_MODEL) are
                missing.

        Note: AgentStore.load_or_create() handles creating an agent from environment
        variables when env_overrides_enabled is True and required env vars
        (LLM_API_KEY and LLM_MODEL) are set.
        """
        agent_store = AgentStore()
        existing_agent = agent_store.load_or_create(
            env_overrides_enabled=env_overrides_enabled
        )
        return existing_agent is None
