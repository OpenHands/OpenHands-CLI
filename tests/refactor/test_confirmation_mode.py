"""Tests for confirmation mode functionality in the refactored UI."""

import uuid
from unittest.mock import MagicMock, patch

from textual.widgets import ListView

from openhands.sdk.security.confirmation_policy import AlwaysConfirm
from openhands_cli.refactor.core.conversation_runner import ConversationRunner
from openhands_cli.refactor.panels.confirmation_panel import (
    ConfirmationPanel,
)
from openhands_cli.refactor.textual_app import OpenHandsApp
from openhands_cli.user_actions.types import UserConfirmation


class TestConversationRunner:
    """Tests for the ConversationRunner."""

    def test_initialization(self):
        """Test that the runner initializes correctly."""
        conversation_id = uuid.uuid4()
        runner = ConversationRunner(conversation_id)

        assert runner.conversation is None
        assert runner.conversation_id == conversation_id
        assert runner.is_confirmation_mode_active is True  # Now starts enabled
        assert runner.is_running is False

    def test_toggle_confirmation_mode(self):
        """Test that confirmation mode can be toggled."""
        conversation_id = uuid.uuid4()
        runner = ConversationRunner(conversation_id)

        # Initially enabled (changed behavior)
        assert runner.is_confirmation_mode_active is True

        # Mock an existing conversation to test policy updates
        mock_conversation = MagicMock()
        runner.conversation = mock_conversation

        # Toggle to disable (since it starts enabled now)
        runner.toggle_confirmation_mode()
        assert runner.is_confirmation_mode_active is False
        # Check that set_confirmation_policy was called with NeverConfirm
        from openhands.sdk.security.confirmation_policy import NeverConfirm

        mock_conversation.set_confirmation_policy.assert_called_with(NeverConfirm())

        # Toggle to enable again
        runner.toggle_confirmation_mode()
        assert runner.is_confirmation_mode_active is True
        # Check that set_confirmation_policy was called with AlwaysConfirm
        mock_conversation.set_confirmation_policy.assert_called_with(AlwaysConfirm())

    def test_policy_change_methods(self):
        """Test the new policy change functionality."""
        conversation_id = uuid.uuid4()
        runner = ConversationRunner(conversation_id)

        # Mock an existing conversation
        mock_conversation = MagicMock()
        runner.conversation = mock_conversation

        # Test _change_confirmation_policy with NeverConfirm
        from openhands.sdk.security.confirmation_policy import (
            ConfirmRisky,
            NeverConfirm,
        )

        runner._change_confirmation_policy(NeverConfirm())
        mock_conversation.set_confirmation_policy.assert_called_with(NeverConfirm())
        assert runner.is_confirmation_mode_active is False

        # Test _change_confirmation_policy with ConfirmRisky
        runner._change_confirmation_policy(ConfirmRisky())
        mock_conversation.set_confirmation_policy.assert_called_with(ConfirmRisky())
        assert runner.is_confirmation_mode_active is True

        # Test _change_confirmation_policy with AlwaysConfirm
        runner._change_confirmation_policy(AlwaysConfirm())
        mock_conversation.set_confirmation_policy.assert_called_with(AlwaysConfirm())
        assert runner.is_confirmation_mode_active is True

    def test_handle_confirmation_request_policy_changes(self):
        """Test that _handle_confirmation_request handles policy changes correctly."""
        conversation_id = uuid.uuid4()
        runner = ConversationRunner(conversation_id)

        # Mock an existing conversation
        mock_conversation = MagicMock()
        runner.conversation = mock_conversation

        # Mock the confirmation callback to return different decisions
        def mock_callback(pending_actions):
            return UserConfirmation.ALWAYS_PROCEED

        runner.set_confirmation_callback(mock_callback)

        # Mock ConversationState.get_unmatched_actions to return some actions
        with patch(
            "openhands.sdk.conversation.state.ConversationState.get_unmatched_actions"
        ) as mock_get_actions:
            mock_get_actions.return_value = [MagicMock()]  # Some pending actions

            # Test ALWAYS_PROCEED changes policy to NeverConfirm
            result = runner._handle_confirmation_request()
            assert result == UserConfirmation.ALWAYS_PROCEED
            assert runner.is_confirmation_mode_active is False

            # Reset for next test
            runner._confirmation_mode_active = True

            # Test CONFIRM_RISKY changes policy to ConfirmRisky
            def mock_callback_risky(pending_actions):
                return UserConfirmation.CONFIRM_RISKY

            runner.set_confirmation_callback(mock_callback_risky)
            result = runner._handle_confirmation_request()
            assert result == UserConfirmation.CONFIRM_RISKY
            assert runner.is_confirmation_mode_active is True


class TestConfirmationPanel:
    """Tests for the ConfirmationPanel widget."""

    def test_initialization(self):
        """Test that the panel initializes with correct data."""
        mock_actions = [MagicMock(), MagicMock()]
        mock_callback = MagicMock()

        panel = ConfirmationPanel(mock_actions, mock_callback)

        assert panel.pending_actions == mock_actions
        assert panel.confirmation_callback == mock_callback

    def test_listview_auto_focus(self):
        """Test that ListView is automatically focused when panel is mounted."""
        mock_actions = [MagicMock()]
        mock_callback = MagicMock()

        panel = ConfirmationPanel(mock_actions, mock_callback)

        # Mock the query_one method to return a mock ListView
        mock_listview = MagicMock()
        panel.query_one = MagicMock(return_value=mock_listview)

        # Call on_mount to trigger auto-focus
        panel.on_mount()

        # Verify that focus was called on the ListView
        panel.query_one.assert_called_once_with("#confirmation-listview", ListView)
        mock_listview.focus.assert_called_once()

    def test_listview_callbacks(self):
        """Test that ListView selections call the callback with correct decisions."""
        mock_actions = [MagicMock()]
        mock_callback = MagicMock()

        panel = ConfirmationPanel(mock_actions, mock_callback)

        # Mock ListView selection events
        mock_accept_item = MagicMock()
        mock_accept_item.id = "accept"

        mock_reject_item = MagicMock()
        mock_reject_item.id = "reject"

        # Test accept selection
        mock_event = MagicMock()
        mock_event.item = mock_accept_item
        panel.on_list_view_selected(mock_event)
        mock_callback.assert_called_with(UserConfirmation.ACCEPT)

        # Test reject selection
        mock_event.item = mock_reject_item
        panel.on_list_view_selected(mock_event)
        mock_callback.assert_called_with(UserConfirmation.REJECT)

        # Test always proceed selection
        mock_always_item = MagicMock()
        mock_always_item.id = "always"
        mock_event.item = mock_always_item
        panel.on_list_view_selected(mock_event)
        mock_callback.assert_called_with(UserConfirmation.ALWAYS_PROCEED)

        # Test confirm risky selection
        mock_risky_item = MagicMock()
        mock_risky_item.id = "risky"
        mock_event.item = mock_risky_item
        panel.on_list_view_selected(mock_event)
        mock_callback.assert_called_with(UserConfirmation.CONFIRM_RISKY)


class TestOpenHandsAppConfirmation:
    """Tests for confirmation mode integration in OpenHandsApp."""

    def test_confirm_command_handler(self):
        """Test that /confirm command toggles confirmation mode."""
        app = OpenHandsApp()

        # Mock the conversation runner
        mock_runner = MagicMock()
        mock_runner.is_confirmation_mode_active = True  # Now starts enabled
        app.conversation_runner = mock_runner

        # Mock the main display
        with patch.object(app, "query_one") as mock_query:
            mock_main_display = MagicMock()
            mock_query.return_value = mock_main_display

            # Call the confirm command handler
            app._handle_confirm_command()

            # Verify that toggle was called
            mock_runner.toggle_confirmation_mode.assert_called_once()

            # Verify that a status message was added
            mock_main_display.mount.assert_called_once()

    def test_confirmation_request_handler_exists(self):
        """Test that confirmation request handler method exists."""
        app = OpenHandsApp()

        # Verify the method exists
        assert hasattr(app, "_handle_confirmation_request")
        assert callable(getattr(app, "_handle_confirmation_request"))

        # Just verify the method signature works
        import inspect

        sig = inspect.signature(app._handle_confirmation_request)
        assert len(sig.parameters) == 1  # pending_actions (self is implicit)


class TestConfirmationIntegration:
    """Integration tests for confirmation mode."""

    def test_app_has_confirm_command(self):
        """Test that the app recognizes /confirm as a valid command."""
        from openhands_cli.refactor.core.commands import (
            get_valid_commands,
            is_valid_command,
        )

        valid_commands = get_valid_commands()
        assert "/confirm" in valid_commands
        assert is_valid_command("/confirm") is True

    def test_app_handles_confirm_command(self):
        """Test that the app can handle the /confirm command."""
        app = OpenHandsApp()

        # Mock the conversation runner
        mock_runner = MagicMock()
        app.conversation_runner = mock_runner

        # Mock the main display and input event
        with patch.object(app, "query_one") as mock_query:
            mock_main_display = MagicMock()
            mock_query.return_value = mock_main_display

            # Test that the command is handled without errors
            app._handle_command("/confirm")

            # Verify that the runner's toggle method was called
            mock_runner.toggle_confirmation_mode.assert_called_once()

    def test_reject_creates_user_reject_observation(self):
        """Test that rejecting actions creates UserRejectObservation events."""
        conversation_id = uuid.uuid4()
        runner = ConversationRunner(conversation_id)

        # Mock conversation with reject_pending_actions method
        mock_conversation = MagicMock()
        runner.conversation = mock_conversation

        # Mock pending actions
        mock_pending_actions = [MagicMock()]

        with patch(
            "openhands.sdk.conversation.state.ConversationState.get_unmatched_actions",
            return_value=mock_pending_actions,
        ):
            # Set up callback that returns REJECT
            def reject_callback(actions):
                return UserConfirmation.REJECT

            runner._confirmation_callback = reject_callback

            # Call the confirmation request handler
            result = runner._handle_confirmation_request()

            # Should return REJECT
            assert result == UserConfirmation.REJECT

            # Should call reject_pending_actions on the conversation
            mock_conversation.reject_pending_actions.assert_called_once_with(
                "User rejected the actions"
            )

    def test_defer_pauses_conversation(self):
        """Test that deferring actions pauses the conversation."""
        conversation_id = uuid.uuid4()
        runner = ConversationRunner(conversation_id)

        # Mock conversation with pause method
        mock_conversation = MagicMock()
        runner.conversation = mock_conversation

        # Mock pending actions
        mock_pending_actions = [MagicMock()]

        with patch(
            "openhands.sdk.conversation.state.ConversationState.get_unmatched_actions",
            return_value=mock_pending_actions,
        ):
            # Set up callback that returns DEFER
            def defer_callback(actions):
                return UserConfirmation.DEFER

            runner._confirmation_callback = defer_callback

            # Call the confirmation request handler
            result = runner._handle_confirmation_request()

            # Should return DEFER
            assert result == UserConfirmation.DEFER

            # Should call pause on the conversation
            mock_conversation.pause.assert_called_once()
