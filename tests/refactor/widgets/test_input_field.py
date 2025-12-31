"""Tests for InputField widget component."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from textual.app import App
from textual.events import Paste
from textual.widgets import TextArea

from openhands_cli.tui.widgets.input_field import InputField, PasteAwareInput


@pytest.fixture
def input_field() -> InputField:
    """Create a fresh InputField instance for each test."""
    return InputField(placeholder="Test placeholder")


@pytest.fixture
def field_with_mocks(input_field: InputField) -> Generator[InputField, None, None]:
    """InputField with its internal widgets and signal mocked out."""
    input_field.input_widget = MagicMock(spec=PasteAwareInput)
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
            input_field.input_widget.focus()
            await pilot.pause()

            # Single-line paste
            paste_event = Paste(text="Single line text")
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Still single-line
            assert not input_field.is_multiline_mode
            assert input_field.input_widget.display
            assert not input_field.textarea_widget.display

    # ------------------------------
    # Shared helper for basic multi-line variants
    # ------------------------------

    async def _assert_multiline_paste_switches_mode(self, paste_text: str) -> None:
        """Shared scenario: multi-line-ish paste should flip to multi-line mode."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method to avoid the #input_area dependency
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            assert not input_field.is_multiline_mode

            input_field.input_widget.focus()
            await pilot.pause()

            paste_event = Paste(text=paste_text)
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Switched to multi-line and content transferred
            assert input_field.is_multiline_mode
            assert not input_field.input_widget.display
            assert input_field.textarea_widget.display
            assert input_field.textarea_widget.text == paste_text

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "paste_text",
        [
            "Line 1\nLine 2\nLine 3",  # Unix newlines
            "Line 1\rLine 2",  # Classic Mac CR
            "Line 1\r\nLine 2\r\nLine 3",  # Windows CRLF
        ],
    )
    async def test_multiline_paste_variants_switch_to_multiline_mode(
        self, paste_text: str
    ) -> None:
        """Any multi-line-ish paste should trigger automatic mode switch."""
        await self._assert_multiline_paste_switches_mode(paste_text)

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

            # Start in single-line mode with initial text + cursor position
            assert not input_field.is_multiline_mode
            input_field.input_widget.value = initial_text
            input_field.input_widget.cursor_position = cursor_pos

            input_field.input_widget.focus()
            await pilot.pause()

            paste_event = Paste(text=paste_text)
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should have switched to multi-line mode with correct final text
            assert input_field.is_multiline_mode
            assert input_field.textarea_widget.text == expected_text

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
            input_field.textarea_widget.text = initial_content

            input_field.textarea_widget.focus()
            await pilot.pause()

            # Paste into input_widget (not focused) – should be ignored
            paste_event = Paste(text="Pasted\nContent")
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            assert input_field.is_multiline_mode
            assert input_field.textarea_widget.text == initial_content

    @pytest.mark.asyncio
    async def test_empty_paste_does_not_switch_mode(self) -> None:
        """Empty paste should not trigger mode switch."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            assert not input_field.is_multiline_mode

            input_field.input_widget.focus()
            await pilot.pause()

            paste_event = Paste(text="")
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Still single-line, nothing changed
            assert not input_field.is_multiline_mode
