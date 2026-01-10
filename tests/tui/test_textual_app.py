"""Tests for OpenHandsApp in textual_app.py."""

from unittest.mock import Mock

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
