"""Tests for InputField widget component."""

import pytest
from unittest.mock import Mock, patch
from textual.app import App
from textual.widgets import Input, TextArea

from openhands_cli.refactor.widgets.input_field import InputField


class TestInputField:
    """Test suite for InputField widget."""

    @pytest.fixture
    def input_field(self):
        """Create an InputField instance for testing."""
        return InputField(placeholder="Test placeholder")

    @pytest.fixture
    def app_with_input_field(self, input_field):
        """Create a Textual app with InputField for integration testing."""

        class TestApp(App):
            def compose(self):
                yield input_field

        app = TestApp()
        return app, input_field

    def test_toggle_input_mode_switches_between_single_and_multiline(self, input_field):
        """Verify F1 key binding toggles between single-line and multi-line modes."""
        # Initially in single-line mode
        assert not input_field.is_multiline_mode

        # Mock the widgets to avoid Textual rendering issues
        input_field.input_widget = Mock(spec=Input)
        input_field.textarea_widget = Mock(spec=TextArea)
        input_field.mutliline_mode_status = Mock()

        # Toggle to multi-line mode
        input_field.action_toggle_input_mode()

        assert input_field.is_multiline_mode
        input_field.input_widget.display = False
        input_field.textarea_widget.display = True
        input_field.textarea_widget.focus.assert_called_once()
        input_field.mutliline_mode_status.publish.assert_called_with(True)

        # Toggle back to single-line mode
        input_field.action_toggle_input_mode()

        assert not input_field.is_multiline_mode
        input_field.textarea_widget.display = False
        input_field.input_widget.display = True
        input_field.input_widget.focus.assert_called_once()

    @pytest.mark.parametrize(
        "content,expected_single,expected_multi",
        [
            ("Simple text", "Simple text", "Simple text"),
            ("Line 1\\nLine 2", "Line 1\\nLine 2", "Line 1\nLine 2"),
            ("Multi\nLine\nText", "Multi\\nLine\\nText", "Multi\nLine\nText"),
            ("", "", ""),
            ("\\n\\n", "\\n\\n", "\n\n"),
        ],
    )
    def test_content_preserved_during_mode_switches(
        self, input_field, content, expected_single, expected_multi
    ):
        """Verify content is preserved with proper newline conversion during mode switches."""
        # Mock the widgets
        input_field.input_widget = Mock(spec=Input)
        input_field.textarea_widget = Mock(spec=TextArea)
        input_field.mutliline_mode_status = Mock()

        # Start with content in single-line mode
        input_field.input_widget.value = content
        input_field.is_multiline_mode = False

        # Switch to multi-line mode
        input_field.action_toggle_input_mode()

        # Verify content conversion to multi-line format
        input_field.textarea_widget.text = expected_multi
        assert input_field.stored_content == expected_multi

        # Switch back to single-line mode
        input_field.textarea_widget.text = expected_multi
        input_field.action_toggle_input_mode()

        # Verify content conversion back to single-line format
        assert input_field.stored_content == expected_single

    def test_focus_management_during_mode_switches(self, input_field):
        """Verify correct widget receives focus after toggling modes."""
        # Mock the widgets
        input_field.input_widget = Mock(spec=Input)
        input_field.textarea_widget = Mock(spec=TextArea)
        input_field.mutliline_mode_status = Mock()

        # Initially in single-line mode
        assert not input_field.is_multiline_mode

        # Toggle to multi-line mode
        input_field.action_toggle_input_mode()
        input_field.textarea_widget.focus.assert_called_once()

        # Toggle back to single-line mode
        input_field.action_toggle_input_mode()
        input_field.input_widget.focus.assert_called_once()

    @pytest.mark.parametrize(
        "content,should_submit",
        [
            ("Valid content", True),
            ("  Valid with spaces  ", True),
            ("", False),
            ("   ", False),
            ("\t\n  \t", False),
        ],
    )
    def test_single_line_input_submission(self, input_field, content, should_submit):
        """Verify Enter key submits content in single-line mode and clears input."""
        # Mock the widgets and message posting
        input_field.input_widget = Mock(spec=Input)
        input_field.post_message = Mock()
        input_field.is_multiline_mode = False

        # Create mock event
        mock_event = Mock()
        mock_event.value = content

        # Trigger submission
        input_field.on_input_submitted(mock_event)

        if should_submit:
            # Verify input was cleared and message posted
            assert input_field.input_widget.value == ""
            input_field.post_message.assert_called_once()

            # Verify message content
            call_args = input_field.post_message.call_args[0][0]
            assert isinstance(call_args, InputField.Submitted)
            assert call_args.content == content.strip()
        else:
            # Verify no submission occurred
            input_field.post_message.assert_not_called()

    @pytest.mark.parametrize(
        "content,should_submit",
        [
            ("Valid content", True),
            ("Multi\nLine\nContent", True),
            ("  Valid with spaces  ", True),
            ("", False),
            ("   ", False),
            ("\t\n  \t", False),
        ],
    )
    def test_multiline_textarea_submission(self, input_field, content, should_submit):
        """Verify Ctrl+J submits content in multi-line mode, clears textarea, and switches to single-line."""
        # Mock the widgets and methods
        input_field.textarea_widget = Mock(spec=TextArea)
        input_field.textarea_widget.text = content
        input_field.post_message = Mock()
        input_field.action_toggle_input_mode = Mock()
        input_field.is_multiline_mode = True

        # Trigger submission
        input_field.action_submit_textarea()

        if should_submit:
            # Verify textarea was cleared
            assert input_field.textarea_widget.text == ""

            # Verify mode toggle was called
            input_field.action_toggle_input_mode.assert_called_once()

            # Verify message was posted
            input_field.post_message.assert_called_once()

            # Verify message content
            call_args = input_field.post_message.call_args[0][0]
            assert isinstance(call_args, InputField.Submitted)
            assert call_args.content == content.strip()
        else:
            # Verify no submission occurred
            input_field.post_message.assert_not_called()
            input_field.action_toggle_input_mode.assert_not_called()

    def test_empty_content_not_submitted(self, input_field):
        """Verify empty or whitespace-only content is not submitted in either mode."""
        # Mock the widgets
        input_field.input_widget = Mock(spec=Input)
        input_field.textarea_widget = Mock(spec=TextArea)
        input_field.post_message = Mock()

        # Test single-line mode with empty content
        input_field.is_multiline_mode = False
        mock_event = Mock()
        mock_event.value = "   "
        input_field.on_input_submitted(mock_event)
        input_field.post_message.assert_not_called()

        # Test multi-line mode with empty content
        input_field.is_multiline_mode = True
        input_field.textarea_widget.text = "\t\n  "
        input_field.action_submit_textarea()
        input_field.post_message.assert_not_called()

    @pytest.mark.parametrize(
        "mode,widget_content,expected",
        [
            (False, "Single line content", "Single line content"),
            (True, "Multi\nline\ncontent", "Multi\nline\ncontent"),
            (False, "", ""),
            (True, "", ""),
        ],
    )
    def test_get_current_value_returns_correct_content_for_both_modes(
        self, input_field, mode, widget_content, expected
    ):
        """Verify get_current_value() returns correct content from active widget."""
        # Mock the widgets
        input_field.input_widget = Mock(spec=Input)
        input_field.textarea_widget = Mock(spec=TextArea)

        input_field.is_multiline_mode = mode

        if mode:
            input_field.textarea_widget.text = widget_content
        else:
            input_field.input_widget.value = widget_content

        result = input_field.get_current_value()
        assert result == expected

    @pytest.mark.parametrize("mode", [False, True])
    def test_clear_method_clears_active_widget(self, input_field, mode):
        """Verify clear() method clears content of currently active widget."""
        # Mock the widgets
        input_field.input_widget = Mock(spec=Input)
        input_field.textarea_widget = Mock(spec=TextArea)

        input_field.is_multiline_mode = mode

        # Set initial content
        if mode:
            input_field.textarea_widget.text = "Some content"
        else:
            input_field.input_widget.value = "Some content"

        # Clear the content
        input_field.clear()

        # Verify correct widget was cleared
        if mode:
            assert input_field.textarea_widget.text == ""
        else:
            assert input_field.input_widget.value == ""

    def test_multiline_mode_status_signal_published(self, input_field):
        """Verify multiline mode status signal is published when toggling modes."""
        # Mock the widgets and signal
        input_field.input_widget = Mock(spec=Input)
        input_field.textarea_widget = Mock(spec=TextArea)
        input_field.mutliline_mode_status = Mock()

        # Initially in single-line mode
        assert not input_field.is_multiline_mode

        # Toggle to multi-line mode
        input_field.action_toggle_input_mode()
        input_field.mutliline_mode_status.publish.assert_called_with(True)

        # Reset mock
        input_field.mutliline_mode_status.reset_mock()

        # Toggle back to single-line mode
        input_field.action_toggle_input_mode()
        input_field.mutliline_mode_status.publish.assert_called_with(False)

    @pytest.mark.parametrize("mode", [False, True])
    def test_focus_input_method_focuses_correct_widget(self, input_field, mode):
        """Verify focus_input() method focuses correct widget based on current mode."""
        # Mock the widgets
        input_field.input_widget = Mock(spec=Input)
        input_field.textarea_widget = Mock(spec=TextArea)

        input_field.is_multiline_mode = mode

        # Call focus_input
        input_field.focus_input()

        # Verify correct widget was focused
        if mode:
            input_field.textarea_widget.focus.assert_called_once()
            input_field.input_widget.focus.assert_not_called()
        else:
            input_field.input_widget.focus.assert_called_once()
            input_field.textarea_widget.focus.assert_not_called()

    def test_initialization_sets_correct_defaults(self, input_field):
        """Verify InputField initializes with correct default values."""
        assert input_field.placeholder == "Test placeholder"
        assert not input_field.is_multiline_mode
        assert input_field.stored_content == ""
        assert hasattr(input_field, "mutliline_mode_status")

    def test_submitted_message_contains_correct_content(self):
        """Verify Submitted message is created with correct content."""
        content = "Test message content"
        message = InputField.Submitted(content)

        assert message.content == content
        assert isinstance(message, InputField.Submitted)
