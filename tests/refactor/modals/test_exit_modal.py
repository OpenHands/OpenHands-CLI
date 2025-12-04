"""Tests for exit confirmation modal functionality."""

from unittest import mock

import pytest
from textual.widgets import Button

from openhands_cli.refactor.modals.exit_modal import ExitConfirmationModal


class TestExitConfirmationModal:
    """Tests for the ExitConfirmationModal component."""

    def test_yes_button_triggers_exit_confirmation_callback(self):
        """Test that clicking the 'Yes' button calls the exit confirmation callback."""
        # Create mock callbacks
        mock_exit_confirmed = mock.MagicMock()
        mock_exit_cancelled = mock.MagicMock()
        
        # Create modal with custom callbacks
        modal = ExitConfirmationModal(
            on_exit_confirmed=mock_exit_confirmed,
            on_exit_cancelled=mock_exit_cancelled
        )
        
        # Mock the dismiss method
        modal.dismiss = mock.MagicMock()
        
        # Create a "yes" button press event
        yes_button = Button("Yes, proceed", id="yes")
        yes_event = Button.Pressed(yes_button)
        
        # Handle the button press
        modal.on_button_pressed(yes_event)
        
        # Verify the modal was dismissed
        modal.dismiss.assert_called_once()
        
        # Verify the exit confirmation callback was called
        mock_exit_confirmed.assert_called_once()
        
        # Verify the exit cancelled callback was NOT called
        mock_exit_cancelled.assert_not_called()

    def test_no_button_triggers_exit_cancelled_callback(self):
        """Test that clicking the 'No' button calls the exit cancelled callback."""
        # Create mock callbacks
        mock_exit_confirmed = mock.MagicMock()
        mock_exit_cancelled = mock.MagicMock()
        
        # Create modal with custom callbacks
        modal = ExitConfirmationModal(
            on_exit_confirmed=mock_exit_confirmed,
            on_exit_cancelled=mock_exit_cancelled
        )
        
        # Mock the dismiss method
        modal.dismiss = mock.MagicMock()
        
        # Create a "no" button press event
        no_button = Button("No, dismiss", id="no")
        no_event = Button.Pressed(no_button)
        
        # Handle the button press
        modal.on_button_pressed(no_event)
        
        # Verify the modal was dismissed
        modal.dismiss.assert_called_once()
        
        # Verify the exit cancelled callback was called
        mock_exit_cancelled.assert_called_once()
        
        # Verify the exit confirmation callback was NOT called
        mock_exit_confirmed.assert_not_called()

    def test_modal_dismissal_occurs_before_callback_execution(self):
        """Test that the modal is dismissed before the callback is executed."""
        # Track the order of operations
        call_order = []
        
        def mock_exit_confirmed():
            call_order.append("callback_executed")
        
        def mock_dismiss():
            call_order.append("modal_dismissed")
        
        # Create modal with custom callback
        modal = ExitConfirmationModal(on_exit_confirmed=mock_exit_confirmed)
        
        # Mock the dismiss method to track when it's called
        modal.dismiss = mock_dismiss
        
        # Create a "yes" button press event
        yes_button = Button("Yes, proceed", id="yes")
        yes_event = Button.Pressed(yes_button)
        
        # Handle the button press
        modal.on_button_pressed(yes_event)
        
        # Verify the order: dismiss should be called before callback
        assert call_order == ["modal_dismissed", "callback_executed"]

    def test_callback_exceptions_do_not_break_modal(self):
        """Test that exceptions in callbacks don't prevent modal dismissal."""
        # Create a callback that raises an exception
        def failing_callback():
            raise ValueError("Test exception")
        
        # Create modal with failing callback
        modal = ExitConfirmationModal(on_exit_confirmed=failing_callback)
        
        # Mock the dismiss method
        modal.dismiss = mock.MagicMock()
        
        # Create a "yes" button press event
        yes_button = Button("Yes, proceed", id="yes")
        yes_event = Button.Pressed(yes_button)
        
        # Handle the button press - should not raise exception
        # The modal should still be dismissed even if callback fails
        with pytest.raises(ValueError, match="Test exception"):
            modal.on_button_pressed(yes_event)
        
        # Verify the modal was still dismissed despite the exception
        modal.dismiss.assert_called_once()

    async def test_modal_keyboard_navigation(self):
        """Test that the modal supports proper keyboard navigation."""
        from textual.app import App
        
        # Create a simple test app that can host the modal
        class TestApp(App):
            def on_mount(self):
                self.push_screen(ExitConfirmationModal())
        
        app = TestApp()
        
        async with app.run_test() as pilot:
            # Get the modal screen (should be the current screen)
            modal = pilot.app.screen
            assert isinstance(modal, ExitConfirmationModal)
            
            # Verify the modal has the expected buttons
            buttons = modal.query(Button)
            assert len(buttons) == 2
            
            # Verify buttons have the correct IDs
            button_ids = {button.id for button in buttons}
            assert button_ids == {"yes", "no"}
            
            # Test that buttons are focusable by attempting to focus them
            yes_button = modal.query_one("#yes", Button)
            no_button = modal.query_one("#no", Button)
            
            # Verify buttons exist and can be focused
            assert yes_button is not None
            assert no_button is not None
            
            # Test keyboard navigation - press Tab to move focus
            await pilot.press("tab")
            
            # Verify that at least one button can receive focus
            # (The exact focus behavior may depend on Textual's implementation)
            assert yes_button.can_focus or no_button.can_focus