"""Tests for OpenHandsApp in textual_app.py."""

import uuid
from unittest.mock import Mock

from openhands_cli.tui.panels.history_side_panel import HistorySidePanel
from openhands_cli.tui.textual_app import OpenHandsApp


class TestSettingsRestartNotification:
    """Tests for restart notification when saving settings."""

    def test_saving_settings_without_conversation_runner_no_notification(self):
        """Saving settings without conversation_runner does not show notification."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        app.conversation_runner = None
        app.notify = Mock()

        app._notify_restart_required()

        app.notify.assert_not_called()

    def test_saving_settings_with_conversation_runner_shows_notification(self):
        """Saving settings with conversation_runner shows restart notification."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        app.conversation_runner = Mock()
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
        # conversation_runner exists but is not running (so settings can be opened)
        app.conversation_runner = Mock()
        app.conversation_runner.is_running = False
        app.push_screen = Mock()
        app._reload_visualizer = Mock()
        app.notify = Mock()

        app.action_open_settings()

        # Simulate cancel - on_settings_saved callbacks are NOT called
        # Verify notify was never called (callbacks not invoked on cancel)
        app.notify.assert_not_called()


class TestHistoryIntegration:
    """Unit tests for history panel wiring and conversation switching."""

    def test_history_command_calls_toggle(self):
        """`/history` command handler delegates to action_toggle_history."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        app.action_toggle_history = Mock()

        app._handle_history_command()

        app.action_toggle_history.assert_called_once()

    def test_action_toggle_history_calls_panel_toggle(self, monkeypatch):
        """action_toggle_history calls HistorySidePanel.toggle with correct args."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        app.conversation_id = uuid.uuid4()
        app._switch_to_conversation = Mock()

        toggle_mock = Mock()
        monkeypatch.setattr(HistorySidePanel, "toggle", toggle_mock)

        app.action_toggle_history()

        toggle_mock.assert_called_once()
        _app_arg = toggle_mock.call_args[0][0]
        assert _app_arg is app
        assert (
            toggle_mock.call_args[1]["current_conversation_id"] == app.conversation_id
        )
        assert (
            toggle_mock.call_args[1]["on_conversation_selected"]
            == app._switch_to_conversation
        )

    def test_finish_conversation_switch_focuses_input(self):
        """After conversation switch completes, input field receives focus."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        app.main_display = Mock()
        app._dismiss_switch_loading_notification = Mock()
        app.history_current_conversation_signal = Mock()
        app.history_current_conversation_signal.publish = Mock()
        app.notify = Mock()
        app.input_field = Mock()
        app.input_field.focus_input = Mock()

        runner = Mock()
        target_id = uuid.uuid4()

        app._finish_conversation_switch(runner, target_id)

        app.input_field.focus_input.assert_called_once()

    def test_switch_to_conversation_invalid_uuid_shows_error(self):
        """Switching with an invalid UUID shows an error notification."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        app.notify = Mock()

        app._switch_to_conversation("not-a-valid-uuid")

        app.notify.assert_called_once()
        call_kwargs = app.notify.call_args[1]
        assert call_kwargs["severity"] == "error"
        assert "invalid" in call_kwargs["message"].lower()

    def test_switch_to_same_conversation_shows_already_active(self):
        """Switching to the already active conversation shows info notification."""
        app = OpenHandsApp.__new__(OpenHandsApp)
        current_id = uuid.uuid4()
        app.conversation_id = current_id
        app.conversation_runner = None  # No runner, so we skip the "is_running" check
        app.notify = Mock()

        app._switch_to_conversation(current_id.hex)

        app.notify.assert_called_once()
        call_kwargs = app.notify.call_args[1]
        assert call_kwargs["severity"] == "information"
        assert "already active" in call_kwargs["message"].lower()
