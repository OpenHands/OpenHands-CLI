"""Tests for InputField widget component."""

from unittest.mock import Mock

import pytest
from textual.app import App
from textual.events import Paste

from openhands_cli.tui.widgets.user_input.input_field import (
    InputField,
)


@pytest.fixture
def input_field() -> InputField:
    """Create a fresh InputField instance for each test."""
    return InputField(placeholder="Test placeholder")


class TestInputField:
    """Unit tests for InputField that don't require a running app."""

    def test_initialization_sets_correct_defaults(
        self, input_field: InputField
    ) -> None:
        """Verify InputField initializes with correct default values."""
        assert input_field.placeholder == "Test placeholder"
        # Before compose(), is_multiline_mode returns False
        assert input_field.is_multiline_mode is False
        assert hasattr(input_field, "mutliline_mode_status")
        assert hasattr(input_field, "multiline_mode_status")

    def test_submitted_message_contains_correct_content(self) -> None:
        """Submitted message should store the user content as-is."""
        content = "Test message content"
        msg = InputField.Submitted(content)

        assert msg.content == content
        assert isinstance(msg, InputField.Submitted)


class TestInputFieldIntegration:
    """Integration tests for InputField using a test app."""

    @pytest.mark.asyncio
    async def test_toggle_mode_preserves_content(self) -> None:
        """Toggling mode should preserve text content."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Start in single-line mode
            assert not input_field.is_multiline_mode

            # Set some content
            input_field.single_line_widget.text = "Hello World"

            # Toggle to multiline
            input_field.action_toggle_input_mode()
            await pilot.pause()

            assert input_field.is_multiline_mode
            assert input_field.multiline_widget.text == "Hello World"

            # Toggle back to single-line
            input_field.action_toggle_input_mode()
            await pilot.pause()

            assert not input_field.is_multiline_mode
            assert input_field.single_line_widget.text == "Hello World"

    @pytest.mark.asyncio
    async def test_get_current_value_returns_active_mode_text(self) -> None:
        """get_current_value() returns text from the active mode."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # In single-line mode
            input_field.single_line_widget.text = "Single line"
            assert input_field.get_current_value() == "Single line"

            # Toggle to multiline
            input_field.action_toggle_input_mode()
            await pilot.pause()

            input_field.multiline_widget.text = "Multi\nline"
            assert input_field.get_current_value() == "Multi\nline"

    @pytest.mark.asyncio
    async def test_focus_input_focuses_active_mode(self) -> None:
        """focus_input() should focus the current mode's widget."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Focus single-line mode
            input_field.focus_input()
            await pilot.pause()
            assert input_field.single_line_widget.has_focus

            # Toggle to multiline and focus
            input_field.action_toggle_input_mode()
            input_field.focus_input()
            await pilot.pause()
            assert input_field.multiline_widget.has_focus

    @pytest.mark.asyncio
    async def test_submit_from_multiline_mode(self) -> None:
        """Ctrl+J should submit content in multiline mode."""
        app = InputFieldTestApp()
        submitted_messages = []

        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Toggle to multiline
            input_field.action_toggle_input_mode()
            await pilot.pause()

            # Set content
            input_field.multiline_widget.text = "Multi\nline\ncontent"

            # Capture submitted messages
            original_post_message = input_field.post_message

            def capture_message(msg):
                if isinstance(msg, InputField.Submitted):
                    submitted_messages.append(msg)
                return original_post_message(msg)

            input_field.post_message = capture_message

            # Submit
            input_field.action_submit_textarea()
            await pilot.pause()

            assert len(submitted_messages) == 1
            assert submitted_messages[0].content == "Multi\nline\ncontent"
            # Should switch back to single-line mode
            assert not input_field.is_multiline_mode


# Single shared app for all integration tests
class InputFieldTestApp(App):
    def compose(self):
        yield InputField(placeholder="Test input")


class TestInputFieldPasteIntegration:
    """Integration tests for InputField paste functionality using pilot app."""

    @pytest.mark.asyncio
    async def test_single_line_paste_stays_in_single_line_mode(self) -> None:
        """Single-line paste should not trigger mode switch."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Verify we start in single-line mode
            assert not input_field.is_multiline_mode

            # Ensure the input widget has focus
            input_field.single_line_widget.focus()
            await pilot.pause()

            # Single-line paste
            paste_event = Paste(text="Single line text")
            input_field.single_line_widget.post_message(paste_event)
            await pilot.pause()

            # Still single-line
            assert not input_field.is_multiline_mode
            assert input_field.single_line_widget.display
            assert not input_field.multiline_widget.display

    # ------------------------------
    # Shared helper for basic multi-line variants
    # ------------------------------

    async def _assert_multiline_paste_switches_mode(
        self, paste_text: str, expected_text: str
    ) -> None:
        """Shared scenario: multi-line-ish paste should flip to multi-line mode."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method to avoid the #input_area dependency
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            assert not input_field.is_multiline_mode

            input_field.single_line_widget.focus()
            await pilot.pause()

            paste_event = Paste(text=paste_text)
            input_field.single_line_widget.post_message(paste_event)
            await pilot.pause()

            # Switched to multi-line and content transferred
            assert input_field.is_multiline_mode
            assert not input_field.single_line_widget.display
            assert input_field.multiline_widget.display
            assert input_field.multiline_widget.text == expected_text

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "paste_text,expected_text",
        [
            # Unix newlines - already normalized
            ("Line 1\nLine 2\nLine 3", "Line 1\nLine 2\nLine 3"),
            # Classic Mac CR - TextArea normalizes \r to \n
            ("Line 1\rLine 2", "Line 1\nLine 2"),
            # Windows CRLF - TextArea normalizes \r\n to \n
            ("Line 1\r\nLine 2\r\nLine 3", "Line 1\nLine 2\nLine 3"),
        ],
    )
    async def test_multiline_paste_variants_switch_to_multiline_mode(
        self, paste_text: str, expected_text: str
    ) -> None:
        """Any multi-line-ish paste should trigger automatic mode switch.

        TextArea normalizes all newline sequences (\\r\\n, \\r) to \\n.
        """
        await self._assert_multiline_paste_switches_mode(paste_text, expected_text)

    # ------------------------------
    # Parametrized insertion behavior
    # ------------------------------

    async def _assert_paste_insertion_scenario(
        self,
        initial_text: str,
        cursor_pos: int,
        paste_text: str,
        expected_text: str,
    ) -> None:
        """Shared scenario for insert/append/prepend/empty initial text."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method to avoid the #input_area dependency
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Start in single-line mode with initial text
            assert not input_field.is_multiline_mode
            input_field.single_line_widget.text = initial_text

            # Move cursor to position using TextArea's move_cursor method
            # Cursor is positioned at (row, col) - for single line it's (0, col)
            input_field.single_line_widget.move_cursor((0, cursor_pos))

            input_field.single_line_widget.focus()
            await pilot.pause()

            paste_event = Paste(text=paste_text)
            input_field.single_line_widget.post_message(paste_event)
            await pilot.pause()

            # Should have switched to multi-line mode with correct final text
            assert input_field.is_multiline_mode
            assert input_field.multiline_widget.text == expected_text

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "initial_text,cursor_pos,paste_text,expected_text",
        [
            # Insert in the middle: "Hello " + paste + "World"
            (
                "Hello World",
                6,
                "Beautiful\nMulti-line",
                "Hello Beautiful\nMulti-lineWorld",
            ),
            # Prepend to existing text (cursor at beginning)
            (
                "World",
                0,
                "Hello\nBeautiful\n",
                "Hello\nBeautiful\nWorld",
            ),
            # Append to end (cursor at len(initial_text))
            (
                "Hello",
                5,
                "\nBeautiful\nWorld",
                "Hello\nBeautiful\nWorld",
            ),
            # Empty initial text (cursor at 0) – just pasted content
            (
                "",
                0,
                "Line 1\nLine 2\nLine 3",
                "Line 1\nLine 2\nLine 3",
            ),
        ],
    )
    async def test_multiline_paste_insertion_scenarios(
        self,
        initial_text: str,
        cursor_pos: int,
        paste_text: str,
        expected_text: str,
    ) -> None:
        """Multi-line paste should insert at cursor with correct final content."""
        await self._assert_paste_insertion_scenario(
            initial_text=initial_text,
            cursor_pos=cursor_pos,
            paste_text=paste_text,
            expected_text=expected_text,
        )

    # ------------------------------
    # Edge behaviors that don't fit the same shape
    # ------------------------------

    @pytest.mark.asyncio
    async def test_paste_ignored_when_already_in_multiline_mode(self) -> None:
        """Paste events should be ignored when already in multi-line mode."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Switch to multi-line mode first
            input_field.action_toggle_input_mode()
            await pilot.pause()
            assert input_field.is_multiline_mode

            # Initial content in textarea
            initial_content = "Initial content"
            input_field.multiline_widget.text = initial_content

            input_field.multiline_widget.focus()
            await pilot.pause()

            # Paste into input_widget (not focused) – should be ignored
            paste_event = Paste(text="Pasted\nContent")
            input_field.single_line_widget.post_message(paste_event)
            await pilot.pause()

            assert input_field.is_multiline_mode
            assert input_field.multiline_widget.text == initial_content

    @pytest.mark.asyncio
    async def test_empty_paste_does_not_switch_mode(self) -> None:
        """Empty paste should not trigger mode switch."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            assert not input_field.is_multiline_mode

            input_field.single_line_widget.focus()
            await pilot.pause()

            paste_event = Paste(text="")
            input_field.single_line_widget.post_message(paste_event)
            await pilot.pause()

            # Still single-line, nothing changed
            assert not input_field.is_multiline_mode
