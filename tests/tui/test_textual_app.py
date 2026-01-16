"""Tests for OpenHandsApp in textual_app.py."""

import uuid
from unittest.mock import Mock

from openhands_cli.tui.core.conversation_manager import ConversationManager
from openhands_cli.tui.core.conversation_switcher import ConversationSwitcher
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

        toggle_mock = Mock()
        monkeypatch.setattr(HistorySidePanel, "toggle", toggle_mock)

        app.action_toggle_history()

        toggle_mock.assert_called_once()
        _app_arg = toggle_mock.call_args[0][0]
        assert _app_arg is app
        assert (
            toggle_mock.call_args[1]["current_conversation_id"] == app.conversation_id
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

        manager = Mock()
        manager.app = app
        manager.post_to_history_panel = Mock()

        switcher = ConversationSwitcher(manager)
        switcher._dismiss_loading = Mock()

        runner = Mock()
        target_id = uuid.uuid4()

        switcher._finish_switch(runner, target_id)

        app.input_field.focus_input.assert_called_once()
        # Verify that ConversationSwitched message was posted via manager
        manager.post_to_history_panel.assert_called_once()

    def test_switch_to_invalid_uuid_shows_error(self):
        """Switching with an invalid UUID shows an error notification."""
        app = Mock()
        app.notify = Mock()

        manager = Mock()
        manager.app = app

        switcher = ConversationSwitcher(manager)
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

        manager = Mock()
        manager.app = app

        switcher = ConversationSwitcher(manager)
        switcher.switch_to(current_id.hex)

        app.notify.assert_called_once()
        call_kwargs = app.notify.call_args[1]
        assert call_kwargs["severity"] == "information"
        assert "already active" in call_kwargs["message"].lower()


class TestConversationManager:
    """Tests for ConversationManager."""

    def test_create_new_resets_conversation(self):
        """create_new resets conversation state and notifies history panel."""
        app = Mock()
        app.conversation_runner = None
        app.confirmation_panel = None
        app.main_display = Mock()
        app.main_display.children = []
        app.query_one = Mock(return_value=Mock())
        app.notify = Mock()

        manager = ConversationManager(app, Mock())
        manager.store.create.return_value = uuid.uuid4().hex  # type: ignore
        manager.post_to_history_panel = Mock()

        result = manager.create_new()

        assert result is not None
        assert app.conversation_id == result
        manager.post_to_history_panel.assert_called_once()
        app.notify.assert_called_once()

    def test_create_new_blocked_when_running(self):
        """create_new returns None when a conversation is running."""
        app = Mock()
        app.conversation_runner = Mock()
        app.conversation_runner.is_running = True
        app.notify = Mock()

        manager = ConversationManager(app, Mock())

        result = manager.create_new()

        assert result is None
        app.notify.assert_called_once()
        call_kwargs = app.notify.call_args[1]
        assert call_kwargs["severity"] == "error"

    def test_update_title_posts_message(self):
        """update_title posts ConversationTitleUpdated message."""
        app = Mock()
        app.conversation_id = uuid.uuid4()

        manager = ConversationManager(app, Mock())
        manager.post_to_history_panel = Mock()

        manager.update_title("Test title")

        manager.post_to_history_panel.assert_called_once()
