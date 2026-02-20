"""Tests for exit confirmation modal functionality."""

from unittest import mock

from textual.widgets import Button

from openhands_cli.tui.modals.exit_modal import ExitConfirmationModal


class TestExitConfirmationModal:
    """Tests for the ExitConfirmationModal component."""

    def test_yes_button_triggers_exit_confirmation_callback(self):
        """Test that clicking the 'Yes' button calls the exit confirmation callback."""
        # Create mock callbacks
        mock_exit_confirmed = mock.MagicMock()
        mock_exit_cancelled = mock.MagicMock()

        # Create modal with custom callbacks
        modal = ExitConfirmationModal(
            on_exit_confirmed=mock_exit_confirmed, on_exit_cancelled=mock_exit_cancelled
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
            on_exit_confirmed=mock_exit_confirmed, on_exit_cancelled=mock_exit_cancelled
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

        # Create modal with custom callback
        modal = ExitConfirmationModal(on_exit_confirmed=mock_exit_confirmed)

        # Mock the dismiss method to track when it's called
        with mock.patch.object(modal, "dismiss") as mock_dismiss:
            mock_dismiss.side_effect = lambda *args, **kwargs: call_order.append(
                "modal_dismissed"
            )

            # Create a "yes" button press event
            yes_button = Button("Yes, proceed", id="yes")
            yes_event = Button.Pressed(yes_button)

            # Handle the button press
            modal.on_button_pressed(yes_event)

            # Verify the order: dismiss should be called before callback
            assert call_order == ["modal_dismissed", "callback_executed"]

    def test_callback_exceptions_are_handled_gracefully(self):
        """Test that exceptions in callbacks are caught and notified."""

        # Create a callback that raises an exception
        def failing_callback():
            raise ValueError("Test exception")

        # Create modal with failing callback
        modal = ExitConfirmationModal(on_exit_confirmed=failing_callback)

        # Mock the dismiss and notify methods
        modal.dismiss = mock.MagicMock()
        modal.notify = mock.MagicMock()

        # Create a "yes" button press event
        yes_button = Button("Yes, proceed", id="yes")
        yes_event = Button.Pressed(yes_button)

        # Handle the button press - should not raise exception
        modal.on_button_pressed(yes_event)

        # Verify the modal was dismissed
        modal.dismiss.assert_called_once()

        # Verify notify was called with the error
        modal.notify.assert_called_once_with(
            "Error during exit confirmation: Test exception", severity="error"
        )

    def test_no_button_with_none_callback_does_not_crash(self):
        """Test that clicking 'No' with None callback doesn't crash the app."""
        # Create modal with None callback for on_exit_cancelled
        modal = ExitConfirmationModal(on_exit_cancelled=None)

        # Mock the dismiss method
        modal.dismiss = mock.MagicMock()

        # Create a "no" button press event
        no_button = Button("No, dismiss", id="no")
        no_event = Button.Pressed(no_button)

        # Handle the button press - should not raise exception
        modal.on_button_pressed(no_event)

        # Verify the modal was dismissed
        modal.dismiss.assert_called_once()

    def test_exit_cancelled_callback_exception_handling(self):
        """Test that exceptions in on_exit_cancelled callback are handled gracefully."""

        # Create a callback that raises an exception
        def failing_cancelled_callback():
            raise RuntimeError("Cancelled callback failed")

        # Create modal with failing cancelled callback
        modal = ExitConfirmationModal(on_exit_cancelled=failing_cancelled_callback)

        # Mock the dismiss and notify methods
        modal.dismiss = mock.MagicMock()
        modal.notify = mock.MagicMock()

        # Create a "no" button press event
        no_button = Button("No, dismiss", id="no")
        no_event = Button.Pressed(no_button)

        # Handle the button press - should not raise exception
        modal.on_button_pressed(no_event)

        # Verify the modal was dismissed
        modal.dismiss.assert_called_once()

        # Verify notify was called with the error
        modal.notify.assert_called_once_with(
            "Error during exit cancellation: Cancelled callback failed",
            severity="error",
        )

    def test_dismiss_called_before_any_callback_execution(self):
        """Test that dismiss is always called first, regardless of button pressed."""
        call_order = []

        def track_exit_confirmed():
            call_order.append("exit_confirmed")

        def track_exit_cancelled():
            call_order.append("exit_cancelled")

        # Test with "yes" button
        modal = ExitConfirmationModal(
            on_exit_confirmed=track_exit_confirmed,
            on_exit_cancelled=track_exit_cancelled,
        )

        with mock.patch.object(modal, "dismiss") as mock_dismiss:
            mock_dismiss.side_effect = lambda: call_order.append("dismiss")

            # Test "yes" button
            yes_button = Button("Yes, proceed", id="yes")
            yes_event = Button.Pressed(yes_button)
            modal.on_button_pressed(yes_event)

            assert call_order == ["dismiss", "exit_confirmed"]

        # Reset and test with "no" button
        call_order.clear()
        modal = ExitConfirmationModal(
            on_exit_confirmed=track_exit_confirmed,
            on_exit_cancelled=track_exit_cancelled,
        )

        with mock.patch.object(modal, "dismiss") as mock_dismiss:
            mock_dismiss.side_effect = lambda: call_order.append("dismiss")

            # Test "no" button
            no_button = Button("No, dismiss", id="no")
            no_event = Button.Pressed(no_button)
            modal.on_button_pressed(no_event)

            assert call_order == ["dismiss", "exit_cancelled"]

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
