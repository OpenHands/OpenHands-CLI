"""Tests for confirmation mode functionality in the refactored UI."""

from unittest.mock import MagicMock, patch

from openhands_cli.refactor.confirmation_conversation_runner import (
    ConfirmationConversationRunner,
)
from openhands_cli.refactor.confirmation_panel import (
    ConfirmationPanel,
)
from openhands_cli.refactor.textual_app import OpenHandsApp
from openhands_cli.user_actions.types import UserConfirmation


class TestConfirmationConversationRunner:
    """Tests for the ConfirmationConversationRunner."""

    def test_initialization(self):
        """Test that the runner initializes correctly."""
        runner = ConfirmationConversationRunner()

        assert runner.conversation is None
        assert runner.conversation_id is None
        assert runner.is_confirmation_mode_active is False
        assert runner.is_running is False

    def test_toggle_confirmation_mode(self):
        """Test that confirmation mode can be toggled."""
        runner = ConfirmationConversationRunner()

        # Initially disabled
        assert runner.is_confirmation_mode_active is False

        # Set a conversation_id so setup_conversation will be called
        import uuid

        runner.conversation_id = uuid.uuid4()

        # Mock the setup_conversation to avoid actual conversation setup
        with patch(
            "openhands_cli.refactor.confirmation_conversation_runner.setup_conversation"
        ) as mock_setup:
            mock_conversation = MagicMock()
            mock_setup.return_value = mock_conversation

            # Toggle to enable
            runner.toggle_confirmation_mode()
            assert runner.is_confirmation_mode_active is True
            mock_setup.assert_called_with(
                runner.conversation_id, include_security_analyzer=True, visualizer=None
            )

            # Toggle to disable
            runner.toggle_confirmation_mode()
            assert runner.is_confirmation_mode_active is False


class TestConfirmationPanel:
    """Tests for the ConfirmationPanel widget."""

    def test_initialization(self):
        """Test that the panel initializes with correct data."""
        mock_actions = [MagicMock(), MagicMock()]
        mock_callback = MagicMock()

        panel = ConfirmationPanel(mock_actions, mock_callback)

        assert panel.pending_actions == mock_actions
        assert panel.confirmation_callback == mock_callback

    def test_button_callbacks(self):
        """Test that button presses call the callback with correct decisions."""
        mock_actions = [MagicMock()]
        mock_callback = MagicMock()

        panel = ConfirmationPanel(mock_actions, mock_callback)

        # Mock button events
        mock_accept_button = MagicMock()
        mock_accept_button.id = "btn_accept"

        mock_reject_button = MagicMock()
        mock_reject_button.id = "btn_reject"

        # Test accept button
        mock_event = MagicMock()
        mock_event.button = mock_accept_button
        panel.on_button_pressed(mock_event)
        mock_callback.assert_called_with(UserConfirmation.ACCEPT)

        # Test reject button
        mock_event.button = mock_reject_button
        panel.on_button_pressed(mock_event)
        mock_callback.assert_called_with(UserConfirmation.REJECT)


class TestOpenHandsAppConfirmation:
    """Tests for confirmation mode integration in OpenHandsApp."""

    def test_confirm_command_handler(self):
        """Test that /confirm command toggles confirmation mode."""
        app = OpenHandsApp()

        # Mock the conversation runner
        mock_runner = MagicMock()
        mock_runner.is_confirmation_mode_active = False
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
        from openhands_cli.refactor.commands import get_valid_commands, is_valid_command

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
        runner = ConfirmationConversationRunner()
        
        # Mock conversation with reject_pending_actions method
        mock_conversation = MagicMock()
        runner.conversation = mock_conversation
        
        # Mock pending actions
        mock_pending_actions = [MagicMock()]
        
        with patch(
            "openhands.sdk.conversation.state.ConversationState.get_unmatched_actions",
            return_value=mock_pending_actions
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
        runner = ConfirmationConversationRunner()
        
        # Mock conversation with pause method
        mock_conversation = MagicMock()
        runner.conversation = mock_conversation
        
        # Mock pending actions
        mock_pending_actions = [MagicMock()]
        
        with patch(
            "openhands.sdk.conversation.state.ConversationState.get_unmatched_actions",
            return_value=mock_pending_actions
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
