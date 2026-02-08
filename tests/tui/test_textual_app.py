"""Tests for OpenHandsApp in textual_app.py."""

import uuid
from unittest.mock import Mock

from openhands_cli.tui.panels.history_side_panel import HistorySidePanel
from openhands_cli.tui.textual_app import OpenHandsApp


class TestSettingsRestartNotification:
    """Tests for restart notification when saving settings."""

    def test_saving_settings_without_conversation_created_no_notification(self):
        """Saving settings without conversation created does not show notification."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        # Mock conversation_state with is_conversation_created = False
        app.conversation_state = Mock()
        app.conversation_state.is_conversation_created = False

        app.notify = Mock()

        app._notify_restart_required()

        app.notify.assert_not_called()

    def test_saving_settings_with_conversation_created_shows_notification(self):
        """Saving settings with conversation created shows restart notification."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        # Mock conversation_state with is_conversation_created = True
        app.conversation_state = Mock()
        app.conversation_state.is_conversation_created = True

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
        # Mock conversation_state with running = False
        app.conversation_state = Mock()
        app.conversation_state.running = False

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
        """`/history` in InputAreaContainer delegates to action_toggle_history."""
        from openhands_cli.tui.widgets.input_area import InputAreaContainer

        input_area = Mock(spec=InputAreaContainer)
        mock_app = Mock()
        mock_app.action_toggle_history = Mock()
        input_area.app = mock_app

        # Call the real implementation
        InputAreaContainer._command_history(input_area)

        mock_app.action_toggle_history.assert_called_once()

    def test_action_toggle_history_calls_panel_toggle(self, monkeypatch):
        """action_toggle_history calls HistorySidePanel.toggle with correct args."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        # Initialize conversation_state to avoid AttributeError
        from openhands_cli.tui.core.state import ConversationContainer

        app.conversation_state = Mock(spec=ConversationContainer)
        app.conversation_state.conversation_id = uuid.uuid4()

        toggle_mock = Mock()
        monkeypatch.setattr(HistorySidePanel, "toggle", toggle_mock)

        app.action_toggle_history()

        toggle_mock.assert_called_once()
        _app_arg = toggle_mock.call_args[0][0]
        assert _app_arg is app
        assert (
            toggle_mock.call_args[1]["current_conversation_id"]
            == app.conversation_state.conversation_id
        )


class TestInputAreaContainerCommands:
    """Tests for InputAreaContainer command methods."""

    def test_command_new_posts_message(self):
        """_command_new posts CreateConversation message."""
        from openhands_cli.tui.core import CreateConversation
        from openhands_cli.tui.widgets.input_area import InputAreaContainer

        input_area = Mock(spec=InputAreaContainer)
        input_area.post_message = Mock()

        # Call the real implementation
        InputAreaContainer._command_new(input_area)

        # Verify message was posted
        input_area.post_message.assert_called_once()
        posted_message = input_area.post_message.call_args[0][0]
        assert isinstance(posted_message, CreateConversation)
