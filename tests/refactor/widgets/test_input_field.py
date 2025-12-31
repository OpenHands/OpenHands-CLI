"""Tests for InputField widget component.

The InputField has two modes:
1. Single-line mode (default): Uses AutoGrowTextArea with soft wrapping
   - Auto-grows height as text wraps (up to max-height)
   - Enter to submit
2. Multi-line mode: Uses larger TextArea for explicit multiline editing
   - Ctrl+J to submit
   - Toggled with Ctrl+L
"""

from unittest.mock import MagicMock, Mock

import pytest
from textual.app import App
from textual.widgets import TextArea

from openhands_cli.refactor.widgets.input_field import AutoGrowTextArea, InputField


@pytest.fixture
def input_field() -> InputField:
    """Create a fresh InputField instance for each test."""
    return InputField(placeholder="Test placeholder")


@pytest.fixture
def field_with_mocks(input_field: InputField):
    """InputField with its internal widgets mocked out."""
    # Mock the input widget (AutoGrowTextArea)
    input_field.input_widget = MagicMock(spec=AutoGrowTextArea)
    input_field.input_widget.text = ""
    input_field.input_widget.value = ""

    # Mock the textarea widget (TextArea for multiline mode)
    input_field.textarea_widget = MagicMock(spec=TextArea)
    input_field.textarea_widget.text = ""

    # Create mock for the signal and its publish method
    signal_mock = MagicMock()
    publish_mock = MagicMock()
    signal_mock.publish = publish_mock
    input_field.mutliline_mode_status = signal_mock

    return input_field


class TestInputField:
    """Unit tests for InputField widget."""

    def test_initialization_sets_correct_defaults(
        self, input_field: InputField
    ) -> None:
        """Verify InputField initializes with correct default values."""
        assert input_field.placeholder == "Test placeholder"
        # Starts in single-line mode
        assert input_field.is_multiline_mode is False
        assert hasattr(input_field, "mutliline_mode_status")

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
    def test_textarea_submission_in_multiline_mode(
        self,
        field_with_mocks: InputField,
        content: str,
        should_submit: bool,
    ) -> None:
        """
        action_submit_textarea submits trimmed textarea content
        only when non-empty and in multiline mode.
        """
        # Set multiline mode
        field_with_mocks.is_multiline_mode = True
        field_with_mocks.textarea_widget.text = content

        field_with_mocks.post_message = Mock()

        # Mock action_toggle_input_mode since it requires screen access
        field_with_mocks.action_toggle_input_mode = Mock()  # type: ignore[method-assign]

        field_with_mocks.action_submit_textarea()

        if should_submit:
            # Message posted
            field_with_mocks.post_message.assert_called()  # type: ignore
            # Find the Submitted message in calls
            calls = field_with_mocks.post_message.call_args_list  # type: ignore
            submitted_msgs = [
                c[0][0] for c in calls if isinstance(c[0][0], InputField.Submitted)
            ]
            assert len(submitted_msgs) == 1
            assert submitted_msgs[0].content == content.strip()
        else:
            # No Submitted message should be posted for empty content
            calls = field_with_mocks.post_message.call_args_list  # type: ignore
            submitted_msgs = [
                c[0][0] for c in calls if isinstance(c[0][0], InputField.Submitted)
            ]
            assert len(submitted_msgs) == 0

    def test_textarea_submission_ignored_in_single_line_mode(
        self,
        field_with_mocks: InputField,
    ) -> None:
        """action_submit_textarea is ignored when not in multiline mode."""
        field_with_mocks.is_multiline_mode = False
        field_with_mocks.textarea_widget.text = "Some content"

        field_with_mocks.post_message = Mock()

        field_with_mocks.action_submit_textarea()

        # Should not post any message
        field_with_mocks.post_message.assert_not_called()  # type: ignore

    @pytest.mark.parametrize(
        "is_multiline, input_content, textarea_content, expected",
        [
            (False, "Single line", "", "Single line"),
            (True, "", "Multi\nline", "Multi\nline"),
            (False, "", "", ""),
        ],
    )
    def test_get_current_value_returns_appropriate_content(
        self,
        field_with_mocks: InputField,
        is_multiline: bool,
        input_content: str,
        textarea_content: str,
        expected: str,
    ) -> None:
        """get_current_value() returns content from the appropriate widget."""
        field_with_mocks.is_multiline_mode = is_multiline
        field_with_mocks.input_widget.value = input_content
        field_with_mocks.textarea_widget.text = textarea_content
        assert field_with_mocks.get_current_value() == expected

    def test_focus_input_focuses_input_widget_in_single_line_mode(
        self,
        field_with_mocks: InputField,
    ) -> None:
        """focus_input() focuses the input widget in single-line mode."""
        field_with_mocks.is_multiline_mode = False
        field_with_mocks.focus_input()
        field_with_mocks.input_widget.focus.assert_called_once()  # type: ignore[union-attr]

    def test_focus_input_focuses_textarea_in_multiline_mode(
        self,
        field_with_mocks: InputField,
    ) -> None:
        """focus_input() focuses the textarea widget in multiline mode."""
        field_with_mocks.is_multiline_mode = True
        field_with_mocks.focus_input()
        field_with_mocks.textarea_widget.focus.assert_called_once()  # type: ignore[union-attr]

    def test_submitted_message_contains_correct_content(self) -> None:
        """Submitted message should store the user content as-is."""
        content = "Test message content"
        msg = InputField.Submitted(content)

        assert msg.content == content
        assert isinstance(msg, InputField.Submitted)


class TestAutoGrowTextArea:
    """Unit tests for AutoGrowTextArea widget."""

    def test_value_property_returns_text(self) -> None:
        """value property should return the text content."""
        textarea = AutoGrowTextArea(text="Hello world")
        assert textarea.value == "Hello world"

    def test_value_setter_sets_text(self) -> None:
        """value setter should set the text content."""
        textarea = AutoGrowTextArea()
        textarea.value = "New content"
        assert textarea.text == "New content"

    def test_soft_wrap_enabled(self) -> None:
        """AutoGrowTextArea should have soft_wrap enabled."""
        textarea = AutoGrowTextArea()
        assert textarea.soft_wrap is True

    def test_compact_mode_enabled(self) -> None:
        """AutoGrowTextArea should have compact mode enabled."""
        textarea = AutoGrowTextArea()
        assert textarea.compact is True


# Minimal test app without autocomplete for integration tests
class MinimalInputFieldTestApp(App):
    """A minimal app for testing InputField without autocomplete.

    This is needed because the full InputField uses EnhancedAutoComplete
    which requires an Input widget, but AutoGrowTextArea is a TextArea.
    """

    def compose(self):
        # Create a minimal InputField-like setup for testing
        yield AutoGrowTextArea(id="test_textarea", placeholder="Test input")


class TestInputFieldIntegration:
    """Integration tests for InputField functionality using pilot app."""

    @pytest.mark.asyncio
    async def test_auto_grow_textarea_mounts_correctly(self) -> None:
        """AutoGrowTextArea should mount and be accessible."""
        app = MinimalInputFieldTestApp()
        async with app.run_test() as pilot:
            textarea = app.query_one(AutoGrowTextArea)

            # Should have correct properties
            assert textarea is not None
            assert textarea.soft_wrap is True
            assert textarea.compact is True

            await pilot.pause()

    @pytest.mark.asyncio
    async def test_auto_grow_textarea_can_receive_text(self) -> None:
        """AutoGrowTextArea should be able to receive text input."""
        app = MinimalInputFieldTestApp()
        async with app.run_test() as pilot:
            textarea = app.query_one(AutoGrowTextArea)

            # Focus the textarea
            textarea.focus()
            await pilot.pause()

            # Type some text
            await pilot.press("h", "e", "l", "l", "o")
            await pilot.pause()

            # Verify text was entered
            assert "hello" in textarea.text

    @pytest.mark.asyncio
    async def test_auto_grow_textarea_soft_wraps(self) -> None:
        """AutoGrowTextArea should have soft wrapping enabled."""
        app = MinimalInputFieldTestApp()
        async with app.run_test() as pilot:
            textarea = app.query_one(AutoGrowTextArea)

            # Verify soft_wrap is enabled
            assert textarea.soft_wrap is True

            await pilot.pause()

    @pytest.mark.asyncio
    async def test_auto_grow_textarea_value_property(self) -> None:
        """AutoGrowTextArea value property should work like Input widget."""
        app = MinimalInputFieldTestApp()
        async with app.run_test() as pilot:
            textarea = app.query_one(AutoGrowTextArea)

            # Set value using the property
            textarea.value = "Test content"
            await pilot.pause()

            # Verify value is set correctly
            assert textarea.value == "Test content"
            assert textarea.text == "Test content"
