"""Settings screen for OpenHands CLI using Textual.

This module provides a modern form-based settings interface that overlays
the main UI, allowing users to configure their settings including
LLM provider, model, API keys, and advanced options.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, Literal, cast

from textual import getters, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets._select import NoSelection

from openhands.sdk import LLMSummarizingCondenser
from openhands_cli.auth.databricks_pkce import run_browser_pkce_flow
from openhands_cli.stores import AgentStore, CliSettings, CriticSettings
from openhands_cli.tui.modals.settings.choices import (
    _resolve_credentials_for_host,
    get_model_options,
)
from openhands_cli.tui.modals.settings.components import (
    CliSettingsTab,
    CriticSettingsTab,
    SettingsTab,
)
from openhands_cli.tui.modals.settings.utils import SettingsFormData, save_settings


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


class SettingsScreen(ModalScreen):
    """A modal screen for configuring settings."""

    BINDINGS: ClassVar = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+c", "request_quit", "Exit"),
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
    timeout_input: getters.query_one[Input] = getters.query_one("#timeout_input")
    max_tokens_input: getters.query_one[Input] = getters.query_one("#max_tokens_input")
    max_size_input: getters.query_one[Input] = getters.query_one("#max_size_input")
    basic_section: getters.query_one[Container] = getters.query_one("#basic_section")
    advanced_section: getters.query_one[Container] = getters.query_one(
        "#advanced_section"
    )
    databricks_auth_section: getters.query_one[Container] = getters.query_one(
        "#databricks_auth_section"
    )
    refresh_models_button: getters.query_one[Button] = getters.query_one(
        "#refresh_models_button"
    )
    model_refresh_status: getters.query_one[Static] = getters.query_one(
        "#model_refresh_status"
    )
    databricks_m2m_group: getters.query_one[Container] = getters.query_one(
        "#databricks_m2m_group"
    )
    databricks_u2m_group: getters.query_one[Container] = getters.query_one(
        "#databricks_u2m_group"
    )
    databricks_auth_method_select: getters.query_one[Select] = getters.query_one(
        "#databricks_auth_method_select"
    )
    databricks_client_id_input: getters.query_one[Input] = getters.query_one(
        "#databricks_client_id_input"
    )
    databricks_client_secret_input: getters.query_one[Input] = getters.query_one(
        "#databricks_client_secret_input"
    )
    databricks_u2m_client_id_input: getters.query_one[Input] = getters.query_one(
        "#databricks_u2m_client_id_input"
    )
    databricks_u2m_client_secret_input: getters.query_one[Input] = getters.query_one(
        "#databricks_u2m_client_secret_input"
    )
    databricks_u2m_redirect_uri_input: getters.query_one[Input] = getters.query_one(
        "#databricks_u2m_redirect_uri_input"
    )
    databricks_host_input: getters.query_one[Input] = getters.query_one(
        "#databricks_host_input"
    )
    api_key_group: getters.query_one[Container] = getters.query_one("#api_key_group")
    databricks_auth_method_help: getters.query_one[Static] = getters.query_one(
        "#databricks_auth_method_help"
    )

    def __init__(
        self,
        on_settings_saved: Callable[[], None] | list[Callable[[], None]] | None = None,
        on_first_time_settings_cancelled: Callable[[], None] | None = None,
        env_overrides_enabled: bool = False,
        **kwargs,
    ) -> None:
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
        # Suppress on_input_changed side-effects while _load_current_settings
        # is programmatically populating form fields.
        self._loading_settings = False
        self.is_initial_setup = SettingsScreen.is_initial_setup_required(
            env_overrides_enabled=env_overrides_enabled
        )

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
        # Load CLI settings once for initializing both tabs
        cli_settings = CliSettings.load()

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
                        yield CliSettingsTab(initial_settings=cli_settings)

                    # Critic Settings Tab - only show if not first-time setup
                    with TabPane("Critic", id="critic_settings_tab"):
                        yield CriticSettingsTab(initial_settings=cli_settings.critic)

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
        # Render footer for bindings - outside settings_container for proper positioning
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the form with current settings."""
        self._load_current_settings()
        self._update_advanced_visibility()
        self._update_databricks_visibility()
        self._update_field_dependencies()

    def on_show(self) -> None:
        """Reload settings when the screen is shown."""
        # Only reload if we don't have current settings loaded
        # This prevents unnecessary clearing when returning from modals
        if not self.current_agent:
            self._clear_form()
            self._load_current_settings()
            self._update_advanced_visibility()
            self._update_databricks_visibility()
            self._update_field_dependencies()

    def _clear_form(self) -> None:
        """Clear all form values before reloading."""
        self.api_key_input.value = ""
        self.api_key_input.placeholder = "Enter your API key"

        self.custom_model_input.value = ""
        self.base_url_input.value = ""
        self.mode_select.value = "basic"
        self.provider_select.clear()
        self.model_select.clear()
        self.memory_select.value = True
        self.timeout_input.value = ""
        self.max_tokens_input.value = ""
        self.max_size_input.value = ""
        try:
            self.databricks_auth_method_select.value = "u2m"
            self.databricks_client_id_input.value = ""
            self.databricks_client_secret_input.value = ""
            self.databricks_client_secret_input.placeholder = (
                "service-principal client secret"
            )
            self.databricks_u2m_client_id_input.value = ""
            self.databricks_u2m_client_secret_input.value = ""
            self.databricks_u2m_redirect_uri_input.value = ""
            self.databricks_host_input.value = ""
            self.databricks_host_input.placeholder = (
                "https://adb-1234567890.cloud.databricks.com"
            )
        except Exception:
            pass

    def _load_current_settings(self) -> None:
        """Load current settings into the form."""
        if not self.current_agent:
            return
        self._loading_settings = True
        try:
            self._load_current_settings_inner()
        finally:
            self._loading_settings = False

    def _load_current_settings_inner(self) -> None:
        """Inner implementation — called only while _loading_settings is True."""

        llm = self.current_agent.llm

        # Determine if we're in advanced mode.
        # Databricks LLMs always populate base_url (mirrors workspace host) but
        # are a first-class basic-mode provider, so we exclude them from the
        # advanced-mode heuristic.
        is_databricks = getattr(llm, "provider", None) == "databricks"
        self.is_advanced_mode = bool(llm.base_url) and not is_databricks
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
                # Databricks options use full FMAPI ids as values; other providers
                # use the short model name only.
                target_value = llm.model if provider == "databricks" else model
                try:
                    self.model_select.value = target_value
                except Exception:
                    # The saved model is not yet in the option list — this happens
                    # when a discovered-only model was saved and credentials are
                    # not yet resolved at load time. Show it as the sole option so
                    # the user sees their current selection without crashing.
                    # _refresh_databricks_models() will repopulate the full list
                    # once the workspace host and auth fields are filled in.
                    short_label = target_value.split("/", 1)[-1]
                    self.model_select.set_options(
                        [(f"{short_label} (saved — re-enter credentials to refresh)", target_value)]
                    )
                    self.model_select.value = target_value

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

        # Timeout (seconds) – show existing value if set
        if llm.timeout is not None:
            self.timeout_input.value = str(llm.timeout)
        else:
            self.timeout_input.value = ""

        # Max tokens (optional) – show existing value if set
        max_input = getattr(llm, "max_input_tokens", None)
        if max_input is not None:
            self.max_tokens_input.value = str(max_input)
        else:
            self.max_tokens_input.value = ""

        # Condenser max size (optional) – show existing value if set
        if (
            self.current_agent
            and self.current_agent.condenser
            and isinstance(self.current_agent.condenser, LLMSummarizingCondenser)
        ):
            self.max_size_input.value = str(self.current_agent.condenser.max_size)
        else:
            self.max_size_input.value = ""

        # Databricks-specific fields: infer the method from the existing LLM.
        try:
            db_client_id = getattr(llm, "databricks_client_id", None)
            db_client_secret = getattr(llm, "databricks_client_secret", None)
            db_u2m_client_id = getattr(llm, "databricks_u2m_client_id", None)
            db_u2m_redirect_uri = getattr(llm, "databricks_u2m_redirect_uri", None)
            db_host = getattr(llm, "databricks_host", None) or llm.base_url

            # Resolve auth method — only u2m and m2m are supported.
            sdk_auth_method = getattr(llm, "auth_method", None)
            if sdk_auth_method == "m2m" or db_client_id:
                method = "m2m"
            else:
                # Default / fallback: U2M (browser OAuth)
                method = "u2m"

            self.databricks_auth_method_select.value = method
            self.databricks_client_id_input.value = db_client_id or ""
            self.databricks_u2m_client_id_input.value = db_u2m_client_id or ""
            self.databricks_u2m_redirect_uri_input.value = db_u2m_redirect_uri or ""
            self.databricks_host_input.value = db_host or ""
            if db_client_secret:
                # Never echo the secret; show a masked hint so the user can
                # leave blank to keep it.
                self.databricks_client_secret_input.placeholder = (
                    "(leave empty to keep existing secret)"
                )
        except Exception:
            pass

        # Update field dependencies and Databricks-specific visibility after
        # loading all values so auth-method-conditional fields render correctly.
        self._update_databricks_visibility()
        self._update_field_dependencies()

        # If we already have a saved Databricks token (from PAT, M2M, or a
        # previous PKCE sign-in), trigger a background model refresh so the
        # live workspace list appears while the user is in settings.
        try:
            is_databricks = getattr(self.current_agent.llm, "provider", None) == "databricks"
            saved_host = getattr(self.current_agent.llm, "databricks_host", None) or \
                         getattr(self.current_agent.llm, "base_url", None)
            if is_databricks and saved_host:
                token_val: str | None = None
                # Priority: stored_u2m_tokens (from PKCE) > api_key (PAT/M2M)
                stored = getattr(self.current_agent.llm, "stored_u2m_tokens", None)
                if stored and getattr(stored, "access_token", None):
                    token_val = stored.access_token
                else:
                    saved_key = self.current_agent.llm.api_key
                    if saved_key:
                        token_val = (
                            saved_key.get_secret_value()
                            if hasattr(saved_key, "get_secret_value")
                            else str(saved_key)
                        )
                if token_val:
                    self._refresh_databricks_models_with_token(saved_host, token_val)
        except Exception:
            pass

    def _get_selected_model_identity(self) -> tuple[str | None, str | None]:
        """Return the currently selected model/base_url identity from the form."""
        mode = self.mode_select.value if hasattr(self.mode_select, "value") else None

        if mode == "advanced":
            custom_model = self.custom_model_input.value.strip()
            base_url = self.base_url_input.value.strip()
            return (custom_model or None, base_url or None)

        if mode == "basic":
            provider = self.provider_select.value
            model = self.model_select.value
            if (
                provider
                and model
                and not isinstance(provider, NoSelection)
                and not isinstance(model, NoSelection)
            ):
                return (f"{provider}/{model}", None)

        return (None, None)

    def _reset_max_tokens_if_model_changed(self) -> None:
        """Clear stale max token overrides when switching to a different model."""
        if self.current_agent is None:
            return

        selected_model, selected_base_url = self._get_selected_model_identity()
        current_llm = self.current_agent.llm
        current_model = current_llm.model or None
        current_base_url = current_llm.base_url or None

        if (selected_model, selected_base_url) != (current_model, current_base_url):
            self.max_tokens_input.value = ""

    def _update_model_options(self, provider: str, credentials=None) -> None:
        """Update model select options based on provider."""
        current_selection = self.model_select.value

        model_options = get_model_options(provider, credentials=credentials)

        if model_options:
            self.model_select.set_options(model_options)

            # Try to preserve the current selection if it's still valid
            if current_selection and not isinstance(current_selection, NoSelection):
                option_values = [option[1] for option in model_options]
                if current_selection in option_values:
                    self.model_select.value = current_selection
        else:
            self.model_select.set_options([("No models available", "")])

        self._reset_max_tokens_if_model_changed()

    def _refresh_databricks_models_with_token(
        self, host: str, access_token: str
    ) -> None:
        """Refresh the model dropdown after successful authentication.

        The full get_picker_entries() network call happens inside the background
        thread. Only the final list is posted to the main thread so the TUI
        stays responsive throughout.
        """
        host_snap = host.strip().rstrip("/")
        token_snap = access_token

        # Show loading state on the button/status if the screen is mounted.
        try:
            self.refresh_models_button.disabled = True
            self.model_refresh_status.update("⟳ Loading models from workspace…")
        except Exception:
            pass

        def _discover() -> None:
            try:
                from openhands.sdk.llm.providers.databricks import (
                    AuthStrategy,
                    DatabricksCredentials,
                )
                creds = DatabricksCredentials(
                    host=host_snap,
                    get_token=lambda t=token_snap: t,
                    auth_method=AuthStrategy.PAT,
                )
                # Heavy network call stays in the background thread.
                model_options = get_model_options("databricks", credentials=creds)
                if model_options:
                    self.call_from_thread(self._apply_model_options, model_options)
                else:
                    self.call_from_thread(
                        self._set_refresh_status,
                        "Could not load workspace models — showing defaults.",
                        True,
                    )
            except Exception as exc:
                self.call_from_thread(
                    self._set_refresh_status,
                    f"Model refresh failed: {exc}",
                    True,
                )

        self.run_worker(_discover, thread=True)

    def _apply_model_options(self, model_options: list[tuple[str, str]]) -> None:
        """Apply a pre-fetched model list to the dropdown (main-thread only)."""
        try:
            current_selection = self.model_select.value
            self.model_select.set_options(model_options)
            if current_selection and not isinstance(current_selection, NoSelection):
                try:
                    self.model_select.value = current_selection
                except Exception:
                    pass
            count = len(model_options)
            self._set_refresh_status(f"✓ {count} models loaded from workspace.", False)
        except Exception:
            self._set_refresh_status("Model list updated.", False)

    def _set_refresh_status(self, message: str, is_error: bool) -> None:
        """Update the refresh status label and re-enable the button."""
        try:
            from rich.markup import escape as _escape
            self.model_refresh_status.update(_escape(message))
            self.refresh_models_button.disabled = not self._is_databricks_selected()
        except Exception:
            pass

    def _trigger_manual_model_refresh(self) -> None:
        """Explicit refresh — reads saved credentials from the current agent."""
        try:
            if not self._is_databricks_selected() or not self.current_agent:
                return
            llm = self.current_agent.llm
            saved_host = (
                getattr(llm, "databricks_host", None)
                or getattr(llm, "base_url", None)
                or ""
            )
            if not saved_host:
                self._set_refresh_status("Workspace Host is required to refresh models.", True)
                return
            # Try stored_u2m_tokens first, then api_key.
            stored = getattr(llm, "stored_u2m_tokens", None)
            token_val: str | None = None
            if stored and getattr(stored, "access_token", None):
                token_val = stored.access_token
            elif llm.api_key:
                token_val = (
                    llm.api_key.get_secret_value()
                    if hasattr(llm.api_key, "get_secret_value")
                    else str(llm.api_key)
                )
            if not token_val:
                self._set_refresh_status(
                    "No credentials saved — sign in first, then refresh.", True
                )
                return
            self._refresh_databricks_models_with_token(saved_host, token_val)
        except Exception as exc:
            self._set_refresh_status(f"Refresh error: {exc}", True)

    def _update_advanced_visibility(self) -> None:
        """Show/hide basic and advanced sections based on mode."""
        if self.is_advanced_mode:
            self.basic_section.display = False
            self.advanced_section.display = True
        else:
            self.basic_section.display = True
            self.advanced_section.display = False

    def _is_databricks_selected(self) -> bool:
        """Return True if the active model is a Databricks FMAPI model.

        In basic mode, that's when ``provider == 'databricks'``. In advanced
        mode, when the custom model starts with ``databricks/``.
        """
        try:
            if self.is_advanced_mode:
                value = self.custom_model_input.value or ""
                return value.strip().startswith("databricks/")
            provider = self.provider_select.value
            return (not isinstance(provider, NoSelection)) and provider == "databricks"
        except Exception:
            return False

    _AUTH_METHOD_HINTS: dict[str, str] = {
        "m2m": (
            "Service Principal auth: provide the Client ID and Secret below. "
            "No extra packages required."
        ),
        # u2m hint is built dynamically in _build_u2m_hint() using the host field.
    }

    def _build_u2m_hint(self) -> str:
        """Return a U2M OAuth app setup hint."""
        host = ""
        redirect_uri = ""
        try:
            host = self.databricks_host_input.value.strip()
            redirect_uri = self.databricks_u2m_redirect_uri_input.value.strip()
        except Exception:
            pass
        host_display = host or "<workspace-host>"
        redirect_display = redirect_uri or "http://localhost:8080/callback"
        return (
            "Browser OAuth (U2M): enter your OAuth App Client ID above, then click Save.\n"
            "After Save, a browser window will open for you to authenticate.\n\n"
            "To create an OAuth app:\n"
            "  1. Go to: https://accounts.cloud.databricks.com/settings/app-connections\n"
            "  2. Add connection → OAuth → set redirect URI:\n"
            f"        {redirect_display}\n"
            "  3. Copy the Client ID here. Client Secret is optional (public app).\n\n"
            f"Workspace host: {host_display}"
        )

    def _update_databricks_visibility(self) -> None:
        """Show the Databricks auth section only for Databricks models.

        Only two auth methods are supported:
        - u2m:  show OAuth app client_id/secret group; hide API key field
        - m2m:  show service-principal client-id/secret group; hide API key
        """
        try:
            is_db = self._is_databricks_selected()
            self.databricks_auth_section.display = is_db

            method = self.databricks_auth_method_select.value
            if isinstance(method, NoSelection) or not method:
                method = "u2m"

            if not is_db:
                self.api_key_group.display = True
                # Hide Databricks-only controls for non-Databricks providers.
                try:
                    self.refresh_models_button.display = False
                    self.model_refresh_status.display = False
                except Exception:
                    pass
                return

            self.databricks_m2m_group.display = method == "m2m"
            self.databricks_u2m_group.display = method == "u2m"

            # Neither U2M nor M2M use the generic API key field.
            self.api_key_group.display = False

            self.databricks_host_input.disabled = False

            # Show the refresh button for Databricks; enable it only when
            # credentials are already saved (so there's a token to use).
            has_saved_creds = bool(
                self.current_agent
                and self.current_agent.llm
                and (
                    getattr(self.current_agent.llm, "stored_u2m_tokens", None)
                    or self.current_agent.llm.api_key
                )
            )
            self.refresh_models_button.display = True
            self.model_refresh_status.display = True
            self.refresh_models_button.disabled = not has_saved_creds

            hint = self._build_u2m_hint() if method == "u2m" else self._AUTH_METHOD_HINTS.get(str(method), "")
            self.databricks_auth_method_help.update(hint)
        except Exception:
            pass

    def _has_existing_api_key(self) -> bool:
        """Check if there's an existing API key in the agent."""
        return bool(
            self.current_agent
            and self.current_agent.llm
            and self.current_agent.llm.api_key
        )

    def _databricks_auth_needs_api_key(self) -> bool:
        """Databricks never needs the generic API key field (U2M and M2M both
        use their own credential fields). Always returns False so downstream
        field-dependency checks don't gate on an invisible API key input."""
        return False

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

            # For Databricks non-PAT auth methods the API key field is hidden.
            # Treat auth as satisfied so downstream fields are not blocked.
            db_no_key_auth = (
                self._is_databricks_selected()
                and not self._databricks_auth_needs_api_key()
            )
            auth_satisfied = bool(
                api_key or self._has_existing_api_key() or db_no_key_auth
            )

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
                        provider and not isinstance(provider, NoSelection)
                    )

                    # API Key: enabled when model is selected (and visible)
                    self.api_key_input.disabled = not (
                        model and not isinstance(model, NoSelection)
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

                    # API Key: enabled when custom model is entered (and visible)
                    self.api_key_input.disabled = not custom_model
                except Exception:
                    pass

            # Memory Condensation: enabled when credentials are satisfied
            self.memory_select.disabled = not auth_satisfied

            # Advanced LLM settings (timeout, max_tokens, max_size):
            # Only enabled in Advanced mode and when credentials are satisfied
            advanced_settings_enabled = is_advanced_mode and auth_satisfied
            self.timeout_input.disabled = not advanced_settings_enabled
            self.max_tokens_input.disabled = not advanced_settings_enabled
            self.max_size_input.disabled = not advanced_settings_enabled

        except Exception:
            # Silently handle errors during initialization
            pass

    def _show_message(self, message: str, is_error: bool = False) -> None:
        """Show a message to the user."""
        if self.message_widget:
            # Escape Rich/Textual markup characters (e.g. { } from Pydantic
            # validation errors) so they render as literal text, not markup.
            from rich.markup import escape as _escape
            self.message_widget.update(_escape(message))
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
            self._reset_max_tokens_if_model_changed()
            self._update_databricks_visibility()
            self._update_field_dependencies()
            self._clear_message()
        elif event.select.id == "provider_select":
            if event.value is not NoSelection:
                self._update_model_options(str(event.value))
            self._update_databricks_visibility()
            self._update_field_dependencies()
            self._clear_message()
        elif event.select.id == "model_select":
            self._reset_max_tokens_if_model_changed()
            self._update_field_dependencies()
            self._clear_message()
        elif event.select.id == "databricks_auth_method_select":
            self._update_databricks_visibility()
            self._clear_message()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input field changes."""
        # Skip side-effects while _load_current_settings is running so
        # programmatic field population doesn't trigger network calls.
        if self._loading_settings:
            return
        if event.input.id in ["custom_model_input", "base_url_input"]:
            self._reset_max_tokens_if_model_changed()
            self._update_field_dependencies()
            self._clear_message()
        elif event.input.id in ["api_key_input"]:
            self._update_field_dependencies()
            self._clear_message()
        if event.input.id == "custom_model_input":
            self._update_databricks_visibility()
        if event.input.id in ("databricks_host_input", "databricks_u2m_redirect_uri_input"):
            # Refresh the U2M hint immediately so it always reflects the
            # current workspace host and redirect URI as the user types.
            try:
                method = self.databricks_auth_method_select.value
                if str(method) == "u2m":
                    self.databricks_auth_method_help.update(self._build_u2m_hint())
            except Exception:
                pass
        # Model discovery is intentionally NOT triggered on host / auth-method
        # changes. The static curated list is shown until the user authenticates,
        # at which point _refresh_databricks_models_with_token() is called with
        # the real access token (see _run_u2m_pkce_flow / PAT save path).

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save_button":
            self._save_settings()
        elif event.button.id == "cancel_button":
            self._handle_cancel()
        elif event.button.id == "refresh_models_button":
            self._trigger_manual_model_refresh()

    def action_cancel(self) -> None:
        """Handle escape key to cancel settings."""
        self._handle_cancel()

    def action_request_quit(self) -> None:
        """Handle ctrl+c - delegate to app's request_quit."""
        app = cast("OpenHandsApp", self.app)
        app.action_request_quit()

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
        # Gather timeout input (may be empty string)
        timeout_input_value = self.timeout_input.value
        # Databricks-specific fields. Only forwarded when the active model is
        # a databricks model; ``resolve_data_fields`` strips them otherwise.
        db_auth_method_value = self.databricks_auth_method_select.value
        db_auth_method = (
            None
            if isinstance(db_auth_method_value, NoSelection)
            else str(db_auth_method_value)
        )
        db_client_id = self.databricks_client_id_input.value or None
        db_client_secret = self.databricks_client_secret_input.value or None
        db_u2m_client_id = self.databricks_u2m_client_id_input.value or None
        db_u2m_client_secret = self.databricks_u2m_client_secret_input.value or None
        db_u2m_redirect_uri = self.databricks_u2m_redirect_uri_input.value or None
        db_host = self.databricks_host_input.value or None
        # AI Gateway host not collected from TUI; read from env var via backend.
        db_ai_gateway_host = None

        form_data = SettingsFormData(
            mode=mode,
            provider=(
                None if isinstance(provider_value, NoSelection) else str(provider_value)
            ),
            model=None if isinstance(model, NoSelection) else str(model),
            custom_model=None if not custom_model else str(custom_model),
            base_url=None if not base_url else str(base_url),
            api_key_input=self.api_key_input.value,
            memory_condensation_enabled=bool(self.memory_select.value),
            timeout=timeout_input_value,
            max_tokens=self.max_tokens_input.value,
            max_size=self.max_size_input.value,
            databricks_auth_method=db_auth_method,  # type: ignore[arg-type]
            databricks_client_id=db_client_id,
            databricks_client_secret_input=db_client_secret,
            databricks_u2m_client_id=db_u2m_client_id,
            databricks_u2m_client_secret_input=db_u2m_client_secret,
            databricks_u2m_redirect_uri=db_u2m_redirect_uri,
            databricks_host=db_host,
            databricks_ai_gateway_host=db_ai_gateway_host,
        )

        # Preserve existing timeout if user entered an invalid value
        # (validator returned None)
        if form_data.timeout is None and self.current_agent:
            form_data.timeout = getattr(self.current_agent.llm, "timeout", None)
        result = save_settings(form_data, self.current_agent)
        if not result.success:
            self._show_message(result.error_message or "Unknown error", is_error=True)
            return

        # Save CLI and Critic settings if not in initial setup mode
        if not self.is_initial_setup:
            try:
                # Get updated fields from each tab
                cli_settings_tab = self.query_one("#cli_settings_tab", TabPane)
                cli_tab = cli_settings_tab.query_one(CliSettingsTab)

                critic_settings_tab = self.query_one("#critic_settings_tab", TabPane)
                critic_tab = critic_settings_tab.query_one(CriticSettingsTab)

                # Load base settings and merge fields from both tabs
                base_settings = CliSettings.load()

                # Update the nested critic settings

                updated_critic = base_settings.critic.model_copy(
                    update=critic_tab.get_updated_fields()
                )

                merged_settings = base_settings.model_copy(
                    update={
                        **cli_tab.get_updated_fields(),
                        "critic": updated_critic,
                    }
                )

                merged_settings.save()

                # Update reactive state to refresh UI components
                self._update_critic_settings(updated_critic)
            except Exception as e:
                self._show_message(
                    f"Settings saved, but CLI settings failed: {str(e)}", is_error=True
                )
                return

        # If Databricks U2M with a client_id is configured, trigger the browser
        # PKCE flow before dismissing so the access token is stored immediately.
        if (
            form_data.databricks_auth_method == "u2m"
            and form_data.databricks_u2m_client_id
            and form_data.databricks_host
        ):
            self._show_message(
                "Settings saved. Opening browser for Databricks sign-in… "
                "(waiting up to 120 s — no need to reselect model after)",
                is_error=False,
            )
            self._run_u2m_pkce_flow(
                host=form_data.databricks_host,
                client_id=form_data.databricks_u2m_client_id,
                client_secret=form_data.databricks_u2m_client_secret_input or None,
                redirect_uri=form_data.databricks_u2m_redirect_uri or None,
            )
            return  # _run_u2m_pkce_flow will dismiss after tokens are obtained

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

    @work(exclusive=True, thread=False)
    async def _run_u2m_pkce_flow(
        self,
        host: str,
        client_id: str,
        client_secret: str | None,
        redirect_uri: str | None = None,
    ) -> None:
        """Start the browser PKCE flow as a background Textual worker.

        On success, updates the saved agent's ``api_key`` with the obtained
        access token and dismisses the settings screen. On failure, shows an
        error message so the user can try again.
        """
        # Parse the port from a custom redirect URI, or default to 8080.
        callback_port = 8080
        if redirect_uri:
            try:
                from urllib.parse import urlparse as _urlparse
                parsed = _urlparse(redirect_uri)
                if parsed.port:
                    callback_port = parsed.port
            except Exception:
                pass
        try:
            tokens = await run_browser_pkce_flow(
                host,
                client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                callback_port=callback_port,
                timeout_s=120.0,
            )
        except TimeoutError as exc:
            self._show_message(str(exc), is_error=True)
            return
        except Exception as exc:
            self._show_message(f"Authentication failed: {exc}", is_error=True)
            return

        # Rebuild DatabricksLLM using stored_u2m_tokens (not api_key).
        #
        # IMPORTANT: model_copy() does NOT re-run Pydantic model validators,
        # so the private _db_credentials / _db_client attributes would be
        # stale. We call create_llm() so _init_databricks() runs fresh.
        #
        # We use stored_u2m_tokens (not api_key) so that:
        # - resolve_credentials picks the U2M path → auth_method=="u2m"
        # - Settings re-opens showing the U2M form (not PAT)
        # - The U2M client ID / redirect URI are preserved for future re-auth
        try:
            from openhands.sdk import create_llm as _create_llm
            from openhands.sdk.llm.providers.databricks.models import (
                StoredU2MTokens as _StoredU2MTokens,
            )

            saved_agent = self.agent_store.load_from_disk()
            if saved_agent is not None:
                old_llm = saved_agent.llm
                databricks_host = (
                    getattr(old_llm, "databricks_host", None)
                    or getattr(old_llm, "base_url", None)
                    or ""
                )
                # Preserve U2M app credentials so settings re-open correctly.
                # databricks_u2m_client_id / _redirect_uri are now fields on
                # DatabricksLLM (added in the SDK), so they round-trip through
                # model_dump / model_validate_json with the agent settings.
                u2m_client_id = getattr(old_llm, "databricks_u2m_client_id", None)
                u2m_redirect_uri = getattr(old_llm, "databricks_u2m_redirect_uri", None)

                create_kwargs: dict = dict(
                    model=old_llm.model,
                    databricks_host=databricks_host,
                    stored_u2m_tokens=_StoredU2MTokens(
                        access_token=tokens["access_token"],
                        refresh_token=tokens.get("refresh_token", ""),
                        expires_at=tokens.get("expires_at", 0.0),
                        client_id=tokens.get("client_id", u2m_client_id or ""),
                        host=tokens.get("host", databricks_host),
                    ),
                    usage_id="agent",
                )
                if u2m_client_id:
                    create_kwargs["databricks_u2m_client_id"] = u2m_client_id
                if u2m_redirect_uri:
                    create_kwargs["databricks_u2m_redirect_uri"] = u2m_redirect_uri
                updated_llm = _create_llm(**create_kwargs)
                updated_agent = saved_agent.model_copy(update={"llm": updated_llm})
                self.agent_store.save(updated_agent)
        except Exception as exc:
            self._show_message(
                f"Signed in but failed to persist token: {exc}", is_error=True
            )
            return

        self._show_message("Signed in to Databricks successfully!", is_error=False)
        import asyncio as _asyncio

        await _asyncio.sleep(1.0)

        # Invoke callbacks then close — dismiss must happen before kicking off
        # the background model-refresh so no exclusive-worker conflict arises.
        for callback in self.on_settings_saved:
            try:
                callback()
            except Exception:
                pass
        self.dismiss(True)

        # Refresh the model dropdown in the background AFTER dismissing so the
        # live workspace list is ready if the user re-opens settings.
        # Uses thread=True but NOT exclusive=True to avoid cancelling the PKCE
        # worker that is still unwinding at this point.
        self._refresh_databricks_models_with_token(host, tokens["access_token"])

    def _update_critic_settings(self, critic_settings: CriticSettings) -> None:
        """Update reactive critic settings in ConversationContainer.

        This triggers automatic UI updates for all components bound to critic_settings.
        """
        try:
            from openhands_cli.tui.core.state import ConversationContainer

            container = self.app.query_one(ConversationContainer)
            container.set_critic_settings(critic_settings)
        except Exception:
            pass  # Container may not exist in all contexts

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
