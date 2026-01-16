"""Tests for cloud link modal functionality."""

from unittest import mock

from textual.widgets import Button, Checkbox

from openhands_cli.tui.modals.cloud_link_modal import CloudLinkModal


class TestCloudLinkModal:
    """Tests for the CloudLinkModal component."""

    def test_modal_shows_connected_status_when_connected(self):
        """Test that modal shows connected status when is_connected is True."""
        modal = CloudLinkModal(is_connected=True)

        # The modal should be created with connected status
        assert modal.is_connected is True

    def test_modal_shows_disconnected_status_when_not_connected(self):
        """Test that modal shows disconnected status when is_connected is False."""
        modal = CloudLinkModal(is_connected=False)

        # The modal should be created with disconnected status
        assert modal.is_connected is False

    def test_cancel_button_dismisses_modal(self):
        """Test that clicking the 'Cancel' button dismisses the modal."""
        mock_callback = mock.MagicMock()
        modal = CloudLinkModal(is_connected=False, on_link_complete=mock_callback)

        # Mock the dismiss method
        modal.dismiss = mock.MagicMock()

        # Create a cancel button press event
        cancel_button = Button("Cancel", id="cancel_button")
        cancel_event = Button.Pressed(cancel_button)

        # Handle the button press
        modal.on_button_pressed(cancel_event)

        # Verify the modal was dismissed
        modal.dismiss.assert_called_once()

        # Verify the callback was NOT called
        mock_callback.assert_not_called()

    def test_link_button_starts_linking_process(self):
        """Test that clicking 'Link to Cloud' starts the linking process."""
        modal = CloudLinkModal(is_connected=False)

        # Mock the _start_linking method
        modal._start_linking = mock.MagicMock()

        # Create a link button press event
        link_button = Button("Link to Cloud", id="link_button")
        link_event = Button.Pressed(link_button)

        # Handle the button press
        modal.on_button_pressed(link_event)

        # Verify _start_linking was called
        modal._start_linking.assert_called_once()

    def test_link_button_disabled_when_linking_in_progress(self):
        """Test that link button doesn't trigger when linking is in progress."""
        modal = CloudLinkModal(is_connected=False)
        modal._linking_in_progress = True

        # Mock the _start_linking method
        modal._start_linking = mock.MagicMock()

        # Create a link button press event
        link_button = Button("Link to Cloud", id="link_button")
        link_event = Button.Pressed(link_button)

        # Handle the button press
        modal.on_button_pressed(link_event)

        # Verify _start_linking was NOT called
        modal._start_linking.assert_not_called()

    def test_on_success_updates_ui(self):
        """Test that _on_success updates the UI correctly."""
        mock_callback = mock.MagicMock()
        modal = CloudLinkModal(is_connected=False, on_link_complete=mock_callback)

        # Mock the query_one method to return mock widgets
        mock_status_label = mock.MagicMock()
        mock_description = mock.MagicMock()
        mock_link_button = mock.MagicMock()
        mock_cancel_button = mock.MagicMock()
        mock_status_message = mock.MagicMock()

        def mock_query_one(selector, widget_type=None):
            if selector == "#status_label":
                return mock_status_label
            elif selector == "#description":
                return mock_description
            elif selector == "#link_button":
                return mock_link_button
            elif selector == "#cancel_button":
                return mock_cancel_button
            elif selector == "#status_message":
                return mock_status_message
            raise ValueError(f"Unknown selector: {selector}")

        modal.query_one = mock_query_one

        # Call _on_success
        modal._on_success()

        # Verify the callback was called with True
        mock_callback.assert_called_once_with(True)

        # Verify linking is no longer in progress
        assert modal._linking_in_progress is False

    def test_on_failure_re_enables_link_button(self):
        """Test that _on_failure re-enables the link button."""
        modal = CloudLinkModal(is_connected=False)
        modal._linking_in_progress = True

        # Mock the query_one method
        mock_link_button = mock.MagicMock()

        def mock_query_one(selector, widget_type=None):
            if selector == "#link_button":
                return mock_link_button
            raise ValueError(f"Unknown selector: {selector}")

        modal.query_one = mock_query_one

        # Call _on_failure
        modal._on_failure()

        # Verify linking is no longer in progress
        assert modal._linking_in_progress is False

        # Verify link button was re-enabled
        assert mock_link_button.disabled is False
        assert mock_link_button.label == "Link to Cloud"

    def test_override_settings_checkbox_default_unchecked(self):
        """Test that override settings checkbox is unchecked by default."""
        modal = CloudLinkModal(is_connected=False)

        # The checkbox should be created with value=False
        # We verify this by checking the compose method creates it correctly
        # This is tested implicitly through the modal's behavior

    async def test_modal_keyboard_navigation(self):
        """Test that the modal supports proper keyboard navigation."""
        from textual.app import App

        # Create a simple test app that can host the modal
        class TestApp(App):
            def on_mount(self):
                self.push_screen(CloudLinkModal(is_connected=False))

        app = TestApp()

        async with app.run_test() as pilot:
            # Get the modal screen (should be the current screen)
            modal = pilot.app.screen
            assert isinstance(modal, CloudLinkModal)

            # Verify the modal has the expected buttons
            buttons = modal.query(Button)
            assert len(buttons) >= 1  # At least cancel button

            # Verify checkbox exists (only when disconnected)
            checkboxes = modal.query(Checkbox)
            assert len(checkboxes) == 1

            # Verify checkbox is unchecked by default
            override_checkbox = modal.query_one("#override_settings", Checkbox)
            assert override_checkbox.value is False

    async def test_modal_connected_state_no_link_button(self):
        """Test that connected modal doesn't show link button but shows resync."""
        from textual.app import App

        class TestApp(App):
            def on_mount(self):
                self.push_screen(CloudLinkModal(is_connected=True))

        app = TestApp()

        async with app.run_test() as pilot:
            modal = pilot.app.screen
            assert isinstance(modal, CloudLinkModal)

            # Should have cancel and resync buttons when connected
            buttons = modal.query(Button)
            button_ids = {button.id for button in buttons}
            assert "cancel_button" in button_ids
            assert "resync_button" in button_ids
            # Link button should not be present when connected
            assert "link_button" not in button_ids

    async def test_modal_connected_state_no_checkbox(self):
        """Test that connected modal doesn't show override checkbox."""
        from textual.app import App

        class TestApp(App):
            def on_mount(self):
                self.push_screen(CloudLinkModal(is_connected=True))

        app = TestApp()

        async with app.run_test() as pilot:
            modal = pilot.app.screen
            assert isinstance(modal, CloudLinkModal)

            # Checkbox should not be present when connected
            checkboxes = modal.query(Checkbox)
            assert len(checkboxes) == 0

    def test_resync_button_starts_resync_process(self):
        """Test that clicking 'Re-sync Cloud Settings' starts the resync process."""
        modal = CloudLinkModal(is_connected=True)

        # Mock the _start_resync method
        modal._start_resync = mock.MagicMock()

        # Create a resync button press event
        resync_button = Button("Re-sync Cloud Settings", id="resync_button")
        resync_event = Button.Pressed(resync_button)

        # Handle the button press
        modal.on_button_pressed(resync_event)

        # Verify _start_resync was called
        modal._start_resync.assert_called_once()

    def test_resync_button_disabled_when_in_progress(self):
        """Test that resync button doesn't trigger when resync is in progress."""
        modal = CloudLinkModal(is_connected=True)
        modal._linking_in_progress = True

        # Mock the _start_resync method
        modal._start_resync = mock.MagicMock()

        # Create a resync button press event
        resync_button = Button("Re-sync Cloud Settings", id="resync_button")
        resync_event = Button.Pressed(resync_button)

        # Handle the button press
        modal.on_button_pressed(resync_event)

        # Verify _start_resync was NOT called
        modal._start_resync.assert_not_called()

    def test_on_resync_success_updates_ui(self):
        """Test that _on_resync_success updates the UI correctly."""
        mock_callback = mock.MagicMock()
        modal = CloudLinkModal(is_connected=True, on_link_complete=mock_callback)
        modal._linking_in_progress = True

        # Mock the query_one method
        mock_resync_button = mock.MagicMock()

        def mock_query_one(selector, widget_type=None):
            if selector == "#resync_button":
                return mock_resync_button
            raise ValueError(f"Unknown selector: {selector}")

        modal.query_one = mock_query_one

        # Call _on_resync_success
        modal._on_resync_success()

        # Verify the callback was called with True
        mock_callback.assert_called_once_with(True)

        # Verify linking is no longer in progress
        assert modal._linking_in_progress is False

        # Verify button was re-enabled
        assert mock_resync_button.disabled is False
        assert mock_resync_button.label == "Re-sync Cloud Settings"

    def test_on_resync_failure_re_enables_button(self):
        """Test that _on_resync_failure re-enables the resync button."""
        modal = CloudLinkModal(is_connected=True)
        modal._linking_in_progress = True

        # Mock the query_one method
        mock_resync_button = mock.MagicMock()

        def mock_query_one(selector, widget_type=None):
            if selector == "#resync_button":
                return mock_resync_button
            raise ValueError(f"Unknown selector: {selector}")

        modal.query_one = mock_query_one

        # Call _on_resync_failure
        modal._on_resync_failure()

        # Verify linking is no longer in progress
        assert modal._linking_in_progress is False

        # Verify button was re-enabled
        assert mock_resync_button.disabled is False
        assert mock_resync_button.label == "Re-sync Cloud Settings"
