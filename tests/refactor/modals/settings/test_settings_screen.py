"""Integration-ish tests for SettingsScreen using a real Textual App + Pilot.

Business logic for validating/saving settings is covered in test_settings_utils.py.
These tests focus on wiring between the UI and that logic.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from textual.app import App, ComposeResult
from textual.css.query import NoMatches
from textual.widgets import Button, Static

from openhands.sdk import LLM, Agent
from openhands_cli.tui.modals.settings import settings_screen as ss
from openhands_cli.tui.modals.settings.settings_screen import SettingsScreen


#
# Test App + fixtures
#


class InMemoryAgentStore:
    """Simple in-memory AgentStore replacement for UI tests."""

    def __init__(self) -> None:
        self._agent: Agent | None = None

    def save(self, agent: Agent) -> None:
        self._agent = agent

    def load(self) -> Agent | None:
        return self._agent


class SettingsTestApp(App):
    """Minimal app that pushes the SettingsScreen on mount."""

    def __init__(self) -> None:
        super().__init__()
        self.settings_screen = SettingsScreen()

    def compose(self) -> ComposeResult:
        # We don't need to yield the modal screen as a widget;
        # it's managed via push_screen.
        yield Static()

    def on_mount(self) -> None:
        # ✅ Push the modal on mount so it’s active
        self.push_screen(self.settings_screen)


@pytest.fixture
def fake_agent_store(monkeypatch) -> InMemoryAgentStore:
    """Patch AgentStore usage inside settings_screen to an in-memory store."""
    store = InMemoryAgentStore()

    # Any AgentStore() inside settings_screen module will now return this store
    monkeypatch.setattr(ss, "AgentStore", lambda: store)
    # Also patch in the SettingsScreen module itself
    monkeypatch.setattr(
        "openhands_cli.tui.modals.settings.settings_screen.AgentStore",
        lambda: store,
    )
    return store


@pytest.fixture
def test_agent() -> Agent:
    """A simple Agent with a known LLM config."""
    llm = LLM(
        model="openai/gpt-4o-mini",
        api_key="test-api-key-12345",
        usage_id="agent",
    )
    return Agent(llm=llm)


@pytest.fixture
async def app(fake_agent_store: InMemoryAgentStore):
    """Provide a running Textual app with SettingsScreen pushed."""
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        yield app, pilot


#
# 1. is_initial_setup_required (no duplication of save_settings logic)
#


@pytest.mark.parametrize(
    "has_agent, expected",
    [
        (False, True),
        (True, False),
    ],
)
def test_is_initial_setup_required(
    fake_agent_store: InMemoryAgentStore, has_agent, expected
):
    if has_agent:
        fake_agent_store.save(Agent(llm=LLM(model="x", api_key="y")))
    else:
        fake_agent_store._agent = None

    assert SettingsScreen.is_initial_setup_required() is expected


#
# 2. Loading settings into the form (basic vs advanced)
#


@pytest.mark.asyncio
async def test_load_current_settings_basic_mode(
    app, fake_agent_store: InMemoryAgentStore, test_agent: Agent
):
    """Basic mode: provider/model + API key placeholder
    + memory flag wired correctly."""
    app_obj, _ = app
    fake_agent_store.save(test_agent)

    screen = app_obj.settings_screen
    assert screen is not None

    # Force a reload to simulate on_mount behavior
    screen.current_agent = fake_agent_store.load()

    with patch.object(ss, "get_model_options") as mock_get_options:
        # Model options don't include provider prefix
        mock_get_options.return_value = [
            ("gpt-4o-mini", "gpt-4o-mini"),
            ("gpt-4o", "gpt-4o"),
        ]
        screen._load_current_settings()

    mode_select = screen.mode_select
    provider_select = screen.provider_select
    model_select = screen.model_select
    api_key_input = screen.api_key_input
    memory_select = screen.memory_select

    assert screen.is_advanced_mode is False
    assert mode_select.value == "basic"
    assert provider_select.value == "openai"
    # Model select value should be model_id without provider prefix
    assert model_select.value == "gpt-4o-mini"

    placeholder = api_key_input.placeholder
    assert placeholder.startswith("Current: tes")
    assert "***" in placeholder
    assert "leave empty to keep current" in placeholder

    # Memory select should reflect presence of condenser (None by default)
    assert memory_select.value is False


@pytest.mark.asyncio
async def test_load_current_settings_advanced_mode(
    app, fake_agent_store: InMemoryAgentStore
):
    """If base_url is set, we treat it as advanced mode
    and populate custom model + base URL."""
    app_obj, _ = app
    llm = LLM(
        model="custom-model",
        api_key="test-key",
        base_url="https://api.example.com/v1",
        usage_id="agent",
    )
    agent = Agent(llm=llm)
    fake_agent_store.save(agent)

    screen = app_obj.settings_screen
    assert screen is not None

    screen.current_agent = fake_agent_store.load()
    screen._load_current_settings()

    assert screen.is_advanced_mode is True
    assert screen.mode_select.value == "advanced"
    assert screen.custom_model_input.value == "custom-model"
    assert screen.base_url_input.value == "https://api.example.com/v1"


#
# 3. Basic ↔ Advanced visibility toggling
#


@pytest.mark.asyncio
async def test_mode_toggle_shows_correct_section(app):
    app_obj, _ = app
    screen = app_obj.settings_screen
    assert screen is not None

    # Start in basic mode
    screen.is_advanced_mode = False
    screen._update_advanced_visibility()
    assert screen.basic_section.display is True
    assert screen.advanced_section.display is False

    # Switch to advanced mode via on_select_changed
    event = SimpleNamespace(
        select=SimpleNamespace(id="mode_select"),
        value="advanced",
    )
    screen.on_select_changed(event)

    assert screen.is_advanced_mode is True
    assert screen.basic_section.display is False
    assert screen.advanced_section.display is True


#
# 4. Dependency chain behavior (real widgets, but direct value mutation)
#


@pytest.mark.asyncio
async def test_cli_settings_tab_not_shown_during_initial_setup(fake_agent_store):
    """CLI Settings tab should NOT be rendered during initial setup."""
    with patch.object(SettingsScreen, "is_initial_setup_required", return_value=True):
        app = SettingsTestApp()

    async with app.run_test():
        screen = app.settings_screen
        assert screen.is_initial_setup is True

        with pytest.raises(NoMatches):
            screen.query_one("#cli_settings_tab")


@pytest.mark.asyncio
async def test_basic_mode_dependency_chain(app):
    """Provider -> model -> API key -> memory enabled chain in basic mode."""
    app_obj, _ = app
    screen = app_obj.settings_screen
    assert screen is not None

    # Basic mode setup
    screen.mode_select.value = "basic"
    screen.provider_select.value = "openai"

    screen.model_select.set_options(
        [("GPT-4o", "openai/gpt-4o"), ("GPT-4o Mini", "openai/gpt-4o-mini")]
    )
    screen.model_select.value = "openai/gpt-4o"

    screen.api_key_input.value = "sk-123"

    screen._update_field_dependencies()

    assert screen.provider_select.disabled is False
    assert screen.model_select.disabled is False
    assert screen.api_key_input.disabled is False
    assert screen.memory_select.disabled is False


@pytest.mark.asyncio
async def test_advanced_mode_dependency_chain(app):
    """Custom model drives base_url + API key + memory in advanced mode."""
    app_obj, _ = app
    screen = app_obj.settings_screen
    assert screen is not None

    screen.mode_select.value = "advanced"
    screen.custom_model_input.value = "my/custom"
    screen.api_key_input.value = "sk-123"

    screen._update_field_dependencies()

    assert screen.custom_model_input.disabled is False
    assert screen.base_url_input.disabled is False
    assert screen.api_key_input.disabled is False
    assert screen.memory_select.disabled is False


#
# 5. Save button wiring: success & error flows
#


@pytest.mark.asyncio
async def test_save_button_success_flow(app, fake_agent_store: InMemoryAgentStore):
    """Clicking Save uses the form values, calls
    save_settings, and dismisses on success."""
    app_obj, pilot = app
    screen = app_obj.settings_screen
    assert screen is not None

    screen.current_agent = Agent(llm=LLM(model="x", api_key="y"))

    # Initialize widgets to known values
    screen.mode_select.value = "basic"
    screen.provider_select.value = "openai"
    # ✅ Model select needs options
    screen.model_select.set_options(
        [("GPT-4o", "openai/gpt-4o"), ("GPT-4o Mini", "openai/gpt-4o-mini")]
    )
    screen.model_select.value = "openai/gpt-4o"

    screen.custom_model_input.value = ""
    screen.base_url_input.value = ""
    screen.api_key_input.value = "sk-123"
    screen.memory_select.value = True

    # Spy on callbacks
    screen._show_message = Mock()
    screen.dismiss = Mock()
    on_saved = Mock()
    screen.on_settings_saved = [on_saved]  # Should be a list of callbacks

    save_button = screen.query_one("#save_button", Button)

    with patch.object(ss, "save_settings") as mock_save:
        mock_save.return_value = SimpleNamespace(success=True, error_message=None)
        await pilot.click(save_button)

    mock_save.assert_called_once()
    screen._show_message.assert_called_once()
    on_saved.assert_called_once()
    screen.dismiss.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_save_button_error_flow(app):
    """On save error, we show an error message and do NOT dismiss."""
    app_obj, pilot = app
    screen = app_obj.settings_screen
    assert screen is not None

    screen.mode_select.value = "basic"
    screen.provider_select.value = "openai"
    # ✅ Model select needs options
    screen.model_select.set_options(
        [("GPT-4o", "openai/gpt-4o"), ("GPT-4o Mini", "openai/gpt-4o-mini")]
    )
    screen.model_select.value = "openai/gpt-4o"

    screen.api_key_input.value = "sk-123"
    screen.memory_select.value = False

    screen._show_message = Mock()
    screen.dismiss = Mock()

    save_button = screen.query_one("#save_button", Button)

    with patch.object(ss, "save_settings") as mock_save:
        mock_save.return_value = SimpleNamespace(
            success=False,
            error_message="boom",
        )
        await pilot.click(save_button)

    screen._show_message.assert_called_once()
    screen.dismiss.assert_not_called()


#
# 6. Cancel handling (button + escape)
#


@pytest.mark.asyncio
async def test_cancel_button_calls_first_time_callback(app):
    app_obj, pilot = app
    screen = app_obj.settings_screen
    assert screen is not None

    callback = Mock()
    screen.on_first_time_settings_cancelled = callback
    screen.is_initial_setup = True
    screen.dismiss = Mock()

    cancel_button = screen.query_one("#cancel_button", Button)
    await pilot.click(cancel_button)

    screen.dismiss.assert_called_once_with(False)
    callback.assert_called_once()


@pytest.mark.asyncio
async def test_escape_triggers_action_cancel(app):
    app_obj, pilot = app
    screen = app_obj.settings_screen
    assert screen is not None

    screen._handle_cancel = Mock()
    await pilot.press("escape")
    screen._handle_cancel.assert_called_once()


#
# 7. Messages: show / clear
#


@pytest.mark.asyncio
async def test_show_and_clear_message(app):
    app_obj, _ = app
    screen = app_obj.settings_screen
    assert screen is not None

    screen.message_widget = Mock()

    screen._show_message("Error!", is_error=True)
    screen.message_widget.update.assert_called_with("Error!")
    screen.message_widget.add_class.assert_called_with("error_message")
    screen.message_widget.remove_class.assert_called_with("success_message")

    screen.message_widget.reset_mock()

    screen._clear_message()
    screen.message_widget.update.assert_called_with("")
    screen.message_widget.remove_class.assert_any_call("error_message")
    screen.message_widget.remove_class.assert_any_call("success_message")
