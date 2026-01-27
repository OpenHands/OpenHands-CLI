"""Tests for OpenHandsApp in textual_app.py."""

import uuid
from unittest.mock import Mock

from openhands_cli.tui.core.conversation_switcher import ConversationSwitcher
from openhands_cli.tui.panels.history_side_panel import HistorySidePanel
from openhands_cli.tui.textual_app import OpenHandsApp


class TestSettingsRestartNotification:
    """Tests for restart notification when saving settings."""

    def test_saving_settings_without_conversation_runner_no_notification(self):
        """Saving settings without conversation_runner does not show notification."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        # Mock app_state for the conversation_runner property
        app.app_state = Mock()
        app.app_state.conversation_runner = None
        app.notify = Mock()

        app._notify_restart_required()

        app.notify.assert_not_called()

    def test_saving_settings_with_conversation_runner_shows_notification(self):
        """Saving settings with conversation_runner shows restart notification."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        # Mock app_state for the conversation_runner property
        app.app_state = Mock()
        app.app_state.conversation_runner = Mock()
        app.notify = Mock()

        app._notify_restart_required()

        app.notify.assert_called_once()
        call_args = app.notify.call_args
        assert "restart" in call_args[0][0].lower()
        assert call_args[1]["severity"] == "information"

    def test_cancelling_settings_does_not_show_notification(self, monkeypatch):
        """Cancelling settings save does not trigger restart notification."""
        from openhands_cli.tui import textual_app as ta

        # Track callbacks passed to SettingsScreen
        captured_on_saved = []

        class MockSettingsScreen:
            def __init__(self, on_settings_saved=None, **kwargs):
                captured_on_saved.extend(on_settings_saved or [])

        monkeypatch.setattr(ta, "SettingsScreen", MockSettingsScreen)

        app = OpenHandsApp.__new__(OpenHandsApp)
        # Mock app_state for the conversation_runner property
        app.app_state = Mock()
        app.app_state.conversation_runner = Mock()
        app.app_state.conversation_runner.is_running = False
        app.push_screen = Mock()
        app._reload_visualizer = Mock()
        app.notify = Mock()
        app.env_overrides_enabled = False

        app.action_open_settings()

        # Simulate cancel - on_settings_saved callbacks are NOT called
        # Verify notify was never called (callbacks not invoked on cancel)
        app.notify.assert_not_called()


class TestHistoryIntegration:
    """Unit tests for history panel wiring and conversation switching."""

    def test_history_command_calls_toggle(self):
        """`/history` command in MainDisplay delegates to action_toggle_history."""
        from openhands_cli.tui.widgets import MainDisplay

        main_display = Mock(spec=MainDisplay)
        mock_app = Mock()
        mock_app.action_toggle_history = Mock()
        main_display.app = mock_app

        # Call the real implementation
        MainDisplay._command_history(main_display)

        mock_app.action_toggle_history.assert_called_once()

    def test_action_toggle_history_calls_panel_toggle(self, monkeypatch):
        """action_toggle_history calls HistorySidePanel.toggle with correct args."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        # Initialize app_state to avoid AttributeError
        from openhands_cli.tui.core.state import AppState

        app.app_state = Mock(spec=AppState)
        app.app_state.conversation_id = uuid.uuid4()

        toggle_mock = Mock()
        monkeypatch.setattr(HistorySidePanel, "toggle", toggle_mock)

        app.action_toggle_history()

        toggle_mock.assert_called_once()
        _app_arg = toggle_mock.call_args[0][0]
        assert _app_arg is app
        assert (
            toggle_mock.call_args[1]["current_conversation_id"]
            == app.app_state.conversation_id
        )


class TestConversationSwitcher:
    """Tests for ConversationSwitcher."""

    def test_finish_switch_focuses_input(self):
        """After conversation switch completes, input field receives focus."""
        # Create mock app and manager
        app = Mock()
        app.main_display = Mock()
        app.notify = Mock()
        app.input_field = Mock()
        app.input_field.focus_input = Mock()
        app.app_state = Mock()  # AppState is now used instead of post_message
        # conversation_id property delegates to app_state
        type(app).conversation_id = property(
            lambda self: self.app_state.conversation_id,
            lambda self, v: setattr(self.app_state, "conversation_id", v),
        )

        switcher = ConversationSwitcher(app)
        switcher._dismiss_loading = Mock()

        runner = Mock()
        target_id = uuid.uuid4()

        switcher._finish_switch(runner, target_id)

        app.input_field.focus_input.assert_called_once()
        # Verify that AppState was updated with the new conversation ID
        assert app.app_state.conversation_id == target_id
        app.app_state.reset_conversation_state.assert_called_once()

    def test_switch_to_invalid_uuid_shows_error(self):
        """Switching with an invalid UUID shows an error notification."""
        app = Mock()
        app.notify = Mock()

        switcher = ConversationSwitcher(app)
        switcher.switch_to("not-a-valid-uuid")

        app.notify.assert_called_once()
        call_kwargs = app.notify.call_args[1]
        assert call_kwargs["severity"] == "error"
        assert "invalid" in call_kwargs["message"].lower()

    def test_switch_to_same_conversation_shows_already_active(self):
        """Switching to the already active conversation shows info notification."""
        current_id = uuid.uuid4()

        app = Mock()
        app.conversation_id = current_id
        app.conversation_runner = None  # No runner, so we skip the "is_running" check
        app.notify = Mock()

        switcher = ConversationSwitcher(app)
        switcher.switch_to(current_id.hex)

        app.notify.assert_called_once()
        call_kwargs = app.notify.call_args[1]
        assert call_kwargs["severity"] == "information"
        assert "already active" in call_kwargs["message"].lower()


class TestMainDisplayCommands:
    """Tests for MainDisplay command methods."""

    def test_command_new_resets_conversation(self):
        """_command_new resets conversation state and updates AppState."""
        from openhands_cli.tui.widgets import MainDisplay

        main_display = Mock(spec=MainDisplay)
        main_display.children = []  # Empty children list

        mock_app = Mock()
        mock_app.conversation_runner = None
        mock_app.confirmation_panel = None
        mock_app.notify = Mock()
        mock_app.app_state = Mock()
        mock_app._store = Mock()
        new_id = uuid.uuid4().hex
        mock_app._store.create.return_value = new_id

        # conversation_id property delegates to app_state
        type(mock_app).conversation_id = property(
            lambda self: self.app_state.conversation_id,
            lambda self, v: setattr(self.app_state, "conversation_id", v),
        )

        # Set up the app and query_one for MainDisplay
        main_display.app = mock_app
        main_display.query_one = Mock(return_value=Mock())
        main_display.scroll_home = Mock()

        # Call the real implementation
        MainDisplay._command_new(main_display)

        # Verify AppState was updated
        assert mock_app.app_state.conversation_id == uuid.UUID(new_id)
        mock_app.app_state.reset_conversation_state.assert_called_once()
        mock_app.notify.assert_called_once()

    def test_command_new_blocked_when_running(self):
        """_command_new shows error when a conversation is running."""
        from openhands_cli.tui.widgets import MainDisplay

        main_display = Mock(spec=MainDisplay)

        mock_app = Mock()
        mock_app.conversation_runner = Mock()
        mock_app.conversation_runner.is_running = True
        mock_app.notify = Mock()

        main_display.app = mock_app

        # Call the real implementation
        MainDisplay._command_new(main_display)

        mock_app.notify.assert_called_once()
        call_kwargs = mock_app.notify.call_args[1]
        assert call_kwargs["severity"] == "error"
