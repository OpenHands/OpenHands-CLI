"""Tests for InputField widget component."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from textual.widgets import Input, TextArea

from openhands_cli.refactor.widgets.input_field import InputField


@pytest.fixture
def input_field() -> InputField:
    """Create a fresh InputField instance for each test."""
    return InputField(placeholder="Test placeholder")


@pytest.fixture
def field_with_mocks(input_field: InputField) -> Generator[InputField, None, None]:
    """InputField with its internal widgets and signal mocked out."""
    input_field.input_widget = MagicMock(spec=Input)
    input_field.textarea_widget = MagicMock(spec=TextArea)

    # Create separate mock objects for focus methods
    input_focus_mock = MagicMock()
    textarea_focus_mock = MagicMock()
    input_field.input_widget.focus = input_focus_mock
    input_field.textarea_widget.focus = textarea_focus_mock

    # Create mock for the signal and its publish method
    signal_mock = MagicMock()
    publish_mock = MagicMock()
    signal_mock.publish = publish_mock
    input_field.mutliline_mode_status = signal_mock

    # Mock the screen and input_area for toggle functionality
    input_area_mock = MagicMock()
    input_area_mock.styles = MagicMock()
    mock_screen = MagicMock()
    mock_screen.query_one.return_value = input_area_mock

    # Use patch to mock the screen property
    with patch.object(type(input_field), "screen", new_callable=lambda: mock_screen):
        yield input_field


class TestInputField:
    def test_initialization_sets_correct_defaults(
        self, input_field: InputField
    ) -> None:
        """Verify InputField initializes with correct default values."""
        assert input_field.placeholder == "Test placeholder"
        assert input_field.is_multiline_mode is False
        assert input_field.stored_content == ""
        assert hasattr(input_field, "mutliline_mode_status")
        # Widgets themselves are created in compose() / on_mount(), so not asserted.

    @pytest.mark.parametrize(
        "mutliline_content, expected_singleline_content",
        [
            ("Simple text", "Simple text"),
            (
                "Line 1\nLine 2",
                "Line 1\\nLine 2",
            ),
            ("Multi\nLine\nText", "Multi\\nLine\\nText"),
            ("", ""),
            ("\n\n", "\\n\\n"),
        ],
    )
    def test_toggle_input_mode_converts_and_toggles_visibility(
        self,
        field_with_mocks: InputField,
        mutliline_content,
        expected_singleline_content,
    ) -> None:
        """Toggling mode converts newline representation and flips displays + signal."""
        # Mock the screen and query_one for input_area
        mock_screen = MagicMock()
        mock_input_area = MagicMock()
        mock_screen.query_one = Mock(return_value=mock_input_area)

        with patch.object(
            type(field_with_mocks),
            "screen",
            new_callable=PropertyMock,
            return_value=mock_screen,
        ):
            # Set mutliline mode
            field_with_mocks.action_toggle_input_mode()
            assert field_with_mocks.is_multiline_mode is True
            assert field_with_mocks.input_widget.display is False
            assert field_with_mocks.textarea_widget.display is True

            # Seed instructions
            field_with_mocks.textarea_widget.text = mutliline_content

            field_with_mocks.action_toggle_input_mode()
            field_with_mocks.mutliline_mode_status.publish.assert_called()  # type: ignore

            # Mutli-line -> single-line
            assert field_with_mocks.input_widget.value == expected_singleline_content

            # Single-line -> multi-line
            field_with_mocks.action_toggle_input_mode()
            field_with_mocks.mutliline_mode_status.publish.assert_called()  # type: ignore

            # Check original content is preserved
            assert field_with_mocks.textarea_widget.text == mutliline_content

    @pytest.mark.parametrize(
        "content, should_submit",
        [
            ("Valid content", True),
            ("  Valid with spaces  ", True),
            ("", False),
            ("   ", False),
            ("\t\n  \t", False),
        ],
    )
    def test_single_line_input_submission(
        self,
        field_with_mocks: InputField,
        content: str,
        should_submit: bool,
    ) -> None:
        """Enter submits trimmed content in single-line mode only when non-empty."""
        field_with_mocks.is_multiline_mode = False
        field_with_mocks.post_message = Mock()

        event = Mock()
        event.value = content

        field_with_mocks.on_input_submitted(event)

        if should_submit:
            field_with_mocks.post_message.assert_called_once()
            msg = field_with_mocks.post_message.call_args[0][0]
            assert isinstance(msg, InputField.Submitted)
            assert msg.content == content.strip()
            # Input cleared after submission
            assert field_with_mocks.input_widget.value == ""
        else:
            field_with_mocks.post_message.assert_not_called()

    @pytest.mark.parametrize(
        "content, should_submit",
        [
            ("Valid content", True),
            ("Multi\nLine\nContent", True),
            ("  Valid with spaces  ", True),
            ("", False),
            ("   ", False),
            ("\t\n  \t", False),
        ],
    )
    def test_multiline_textarea_submission(
        self,
        field_with_mocks: InputField,
        content: str,
        should_submit: bool,
    ) -> None:
        """
        Ctrl+J (action_submit_textarea) submits trimmed textarea content in
        multi-line mode only when non-empty. On submit, textarea is cleared and
        mode toggle is requested.
        """
        field_with_mocks.is_multiline_mode = True
        field_with_mocks.textarea_widget.text = content

        field_with_mocks.post_message = Mock()
        field_with_mocks.action_toggle_input_mode = Mock()

        field_with_mocks.action_submit_textarea()

        if should_submit:
            # Textarea cleared
            assert field_with_mocks.textarea_widget.text == ""
            # Mode toggle requested
            field_with_mocks.action_toggle_input_mode.assert_called_once()
            # Message posted
            field_with_mocks.post_message.assert_called_once()
            msg = field_with_mocks.post_message.call_args[0][0]
            assert isinstance(msg, InputField.Submitted)
            assert msg.content == content.strip()
        else:
            field_with_mocks.post_message.assert_not_called()
            field_with_mocks.action_toggle_input_mode.assert_not_called()

    @pytest.mark.parametrize(
        "is_multiline, widget_content, expected",
        [
            (False, "Single line content", "Single line content"),
            (True, "Multi\nline\ncontent", "Multi\nline\ncontent"),
            (False, "", ""),
            (True, "", ""),
        ],
    )
    def test_get_current_value_uses_active_widget(
        self,
        field_with_mocks: InputField,
        is_multiline: bool,
        widget_content: str,
        expected: str,
    ) -> None:
        """get_current_value() returns content from the active widget."""
        field_with_mocks.is_multiline_mode = is_multiline

        if is_multiline:
            field_with_mocks.textarea_widget.text = widget_content
        else:
            field_with_mocks.input_widget.value = widget_content

        assert field_with_mocks.get_current_value() == expected

    @pytest.mark.parametrize("is_multiline", [False, True])
    def test_focus_input_focuses_active_widget(
        self,
        field_with_mocks: InputField,
        is_multiline: bool,
    ) -> None:
        """focus_input() focuses the widget corresponding to the current mode."""
        field_with_mocks.is_multiline_mode = is_multiline

        field_with_mocks.focus_input()

        if is_multiline:
            field_with_mocks.textarea_widget.focus.assert_called_once()  # type: ignore
            field_with_mocks.input_widget.focus.assert_not_called()  # type: ignore
        else:
            field_with_mocks.input_widget.focus.assert_called_once()  # type: ignore
            field_with_mocks.textarea_widget.focus.assert_not_called()  # type: ignore

    def test_submitted_message_contains_correct_content(self) -> None:
        """Submitted message should store the user content as-is."""
        content = "Test message content"
        msg = InputField.Submitted(content)

        assert msg.content == content
        assert isinstance(msg, InputField.Submitted)
