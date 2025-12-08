"""Tests for InputField widget component."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from textual.widgets import TextArea

from openhands_cli.refactor.widgets.input_field import InputField, PasteAwareInput


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

    @pytest.mark.parametrize(
        "paste_text, should_switch_mode",
        [
            ("Single line text", False),
            ("Multi\nline\ntext", True),
            ("Text with\nnewline", True),
            ("Text with\rcarriage return", True),
            ("Windows\r\nline endings", True),
            ("Mixed\nline\rendings", True),
            ("", False),
            ("Line 1\nLine 2\nLine 3", True),
            ("No newlines here", False),
        ],
    )
    def test_paste_event_handling(
        self,
        field_with_mocks: InputField,
        paste_text: str,
        should_switch_mode: bool,
    ) -> None:
        """Paste events should switch to multi-line mode for multi-line content."""
        # Start in single-line mode
        field_with_mocks.is_multiline_mode = False
        field_with_mocks.action_toggle_input_mode = Mock()

        if should_switch_mode:
            # Set up mock input widget with initial state
            field_with_mocks.input_widget.value = ""  # Start with empty text
            field_with_mocks.input_widget.cursor_position = 0  # Cursor at beginning

            # Create a PasteDetected message (only sent for multi-line content)
            paste_detected_event = Mock(spec=PasteAwareInput.PasteDetected)
            paste_detected_event.text = paste_text

            # Handle the paste detected event
            field_with_mocks.on_paste_aware_input_paste_detected(paste_detected_event)

            # Should set the text in input widget first, then toggle mode
            field_with_mocks.action_toggle_input_mode.assert_called_once()
            # With empty initial text and cursor at 0, input should have paste text
            assert field_with_mocks.input_widget.value == paste_text
        else:
            # For single-line content, no PasteDetected message is sent
            # So we don't call the handler and nothing should happen
            field_with_mocks.action_toggle_input_mode.assert_not_called()

    def test_paste_event_ignored_when_in_multiline_mode(
        self,
        field_with_mocks: InputField,
    ) -> None:
        """Paste events should be ignored when already in multi-line mode."""
        field_with_mocks.is_multiline_mode = True  # Already in multi-line mode
        field_with_mocks.action_toggle_input_mode = Mock()

        # Create a PasteDetected message
        paste_detected_event = Mock(spec=PasteAwareInput.PasteDetected)
        paste_detected_event.text = "Multi\nline\ntext"

        # Handle the paste detected event
        field_with_mocks.on_paste_aware_input_paste_detected(paste_detected_event)

        # Should not switch modes since already in multi-line mode
        field_with_mocks.action_toggle_input_mode.assert_not_called()


class TestInputFieldPasteIntegration:
    """Integration tests for InputField paste functionality using pilot app."""

    @pytest.mark.asyncio
    async def test_single_line_paste_stays_in_single_line_mode(self) -> None:
        """Single-line paste should not trigger mode switch."""
        from textual.app import App
        from textual.events import Paste

        class TestApp(App):
            def compose(self):
                yield InputField(placeholder="Test input")

        app = TestApp()
        async with app.run_test() as pilot:
            # Get the input field
            input_field = app.query_one(InputField)

            # Verify we start in single-line mode
            assert not input_field.is_multiline_mode

            # Ensure the input widget has focus
            input_field.input_widget.focus()
            await pilot.pause()

            # Create and post a single-line paste event to the input widget
            paste_event = Paste(text="Single line text")
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should still be in single-line mode
            assert not input_field.is_multiline_mode
            # Input widget should still be visible
            assert input_field.input_widget.display
            assert not input_field.textarea_widget.display

    @pytest.mark.asyncio
    async def test_multiline_paste_switches_to_multiline_mode(self) -> None:
        """Multi-line paste should trigger automatic mode switch."""
        from unittest.mock import Mock

        from textual.app import App
        from textual.events import Paste

        class TestApp(App):
            def compose(self):
                yield InputField(placeholder="Test input")

        app = TestApp()
        async with app.run_test() as pilot:
            # Get the input field
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method to avoid the #input_area dependency
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Verify we start in single-line mode
            assert not input_field.is_multiline_mode

            # Focus the input widget
            input_field.input_widget.focus()
            await pilot.pause()

            # Create and post a multi-line paste event to the input widget
            multiline_text = "Line 1\nLine 2\nLine 3"
            paste_event = Paste(text=multiline_text)
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should have switched to multi-line mode
            assert input_field.is_multiline_mode
            # Textarea should be visible, input should be hidden
            assert not input_field.input_widget.display
            assert input_field.textarea_widget.display
            # Content should be set in textarea
            assert input_field.textarea_widget.text == multiline_text

    @pytest.mark.asyncio
    async def test_carriage_return_paste_switches_to_multiline_mode(self) -> None:
        """Carriage return paste should trigger automatic mode switch."""
        from unittest.mock import Mock

        from textual.app import App
        from textual.events import Paste

        class TestApp(App):
            def compose(self):
                yield InputField(placeholder="Test input")

        app = TestApp()
        async with app.run_test() as pilot:
            # Get the input field
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method to avoid the #input_area dependency
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Verify we start in single-line mode
            assert not input_field.is_multiline_mode

            # Focus the input widget
            input_field.input_widget.focus()
            await pilot.pause()

            # Create and post a carriage return paste event to the input widget
            cr_text = "Line 1\rLine 2"
            paste_event = Paste(text=cr_text)
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should have switched to multi-line mode
            assert input_field.is_multiline_mode
            # Content should be set in textarea
            assert input_field.textarea_widget.text == cr_text

    @pytest.mark.asyncio
    async def test_windows_line_endings_paste_switches_to_multiline_mode(self) -> None:
        """Windows line endings paste should trigger automatic mode switch."""
        from unittest.mock import Mock

        from textual.app import App
        from textual.events import Paste

        class TestApp(App):
            def compose(self):
                yield InputField(placeholder="Test input")

        app = TestApp()
        async with app.run_test() as pilot:
            # Get the input field
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method to avoid the #input_area dependency
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Verify we start in single-line mode
            assert not input_field.is_multiline_mode

            # Focus the input widget
            input_field.input_widget.focus()
            await pilot.pause()

            # Create and post a Windows line endings paste event to the input widget
            windows_text = "Line 1\r\nLine 2\r\nLine 3"
            paste_event = Paste(text=windows_text)
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should have switched to multi-line mode
            assert input_field.is_multiline_mode
            # Content should be set in textarea
            assert input_field.textarea_widget.text == windows_text

    @pytest.mark.asyncio
    async def test_paste_ignored_when_already_in_multiline_mode(self) -> None:
        """Paste events should be ignored when already in multi-line mode."""
        from unittest.mock import Mock

        from textual.app import App
        from textual.events import Paste

        class TestApp(App):
            def compose(self):
                yield InputField(placeholder="Test input")

        app = TestApp()
        async with app.run_test() as pilot:
            # Get the input field
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method to avoid the #input_area dependency
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Switch to multi-line mode first
            input_field.action_toggle_input_mode()
            await pilot.pause()

            # Verify we're in multi-line mode
            assert input_field.is_multiline_mode

            # Set some initial content
            initial_content = "Initial content"
            input_field.textarea_widget.text = initial_content

            # Focus the textarea widget
            input_field.textarea_widget.focus()
            await pilot.pause()

            # Create and post a multi-line paste event to the input widget
            # (but it's not focused)
            paste_text = "Pasted\nContent"
            paste_event = Paste(text=paste_text)
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should still be in multi-line mode
            assert input_field.is_multiline_mode
            # Content should remain unchanged (paste handler doesn't apply in
            # multi-line mode)
            assert input_field.textarea_widget.text == initial_content

    @pytest.mark.asyncio
    async def test_empty_paste_does_not_switch_mode(self) -> None:
        """Empty paste should not trigger mode switch."""
        from textual.app import App
        from textual.events import Paste

        class TestApp(App):
            def compose(self):
                yield InputField(placeholder="Test input")

        app = TestApp()
        async with app.run_test() as pilot:
            # Get the input field
            input_field = app.query_one(InputField)

            # Verify we start in single-line mode
            assert not input_field.is_multiline_mode

            # Focus the input widget
            input_field.input_widget.focus()
            await pilot.pause()

            # Create and post an empty paste event to the input widget
            paste_event = Paste(text="")
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should still be in single-line mode
            assert not input_field.is_multiline_mode

    @pytest.mark.asyncio
    async def test_multiline_paste_inserts_at_cursor_position(self) -> None:
        """Multi-line paste should insert at cursor position, not replace text."""
        from unittest.mock import Mock

        from textual.app import App
        from textual.events import Paste

        class TestApp(App):
            def compose(self):
                yield InputField(placeholder="Test input")

        app = TestApp()
        async with app.run_test() as pilot:
            # Get the input field
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method to avoid the #input_area dependency
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Verify we start in single-line mode
            assert not input_field.is_multiline_mode

            # Set some initial text and position cursor in the middle
            initial_text = "Hello World"
            input_field.input_widget.value = initial_text
            # Position cursor after "Hello " (position 6)
            cursor_position = 6
            input_field.input_widget.cursor_position = cursor_position

            # Focus the input widget
            input_field.input_widget.focus()
            await pilot.pause()

            # Create and post a multi-line paste event
            paste_text = "Beautiful\nMulti-line"
            paste_event = Paste(text=paste_text)
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should have switched to multi-line mode
            assert input_field.is_multiline_mode

            # Text should be inserted at cursor position, not replaced
            expected_text = "Hello Beautiful\nMulti-lineWorld"
            assert input_field.textarea_widget.text == expected_text

            # Verify the structure: "Hello " + paste_text + "World"
            assert input_field.textarea_widget.text.startswith("Hello Beautiful")
            assert "Multi-line" in input_field.textarea_widget.text
            assert input_field.textarea_widget.text.endswith("World")

    @pytest.mark.asyncio
    async def test_multiline_paste_at_beginning_of_text(self) -> None:
        """Multi-line paste at beginning should prepend to existing text."""
        from unittest.mock import Mock

        from textual.app import App
        from textual.events import Paste

        class TestApp(App):
            def compose(self):
                yield InputField(placeholder="Test input")

        app = TestApp()
        async with app.run_test() as pilot:
            # Get the input field
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Set initial text with cursor at beginning (position 0)
            initial_text = "World"
            input_field.input_widget.value = initial_text
            input_field.input_widget.cursor_position = 0

            # Focus and paste multi-line content
            input_field.input_widget.focus()
            await pilot.pause()

            paste_text = "Hello\nBeautiful\n"
            paste_event = Paste(text=paste_text)
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should switch to multi-line mode with paste prepended
            assert input_field.is_multiline_mode
            expected_text = "Hello\nBeautiful\nWorld"
            assert input_field.textarea_widget.text == expected_text

    @pytest.mark.asyncio
    async def test_multiline_paste_at_end_of_text(self) -> None:
        """Multi-line paste at end should append to existing text."""
        from unittest.mock import Mock

        from textual.app import App
        from textual.events import Paste

        class TestApp(App):
            def compose(self):
                yield InputField(placeholder="Test input")

        app = TestApp()
        async with app.run_test() as pilot:
            # Get the input field
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Set initial text with cursor at end
            initial_text = "Hello"
            input_field.input_widget.value = initial_text
            input_field.input_widget.cursor_position = len(initial_text)

            # Focus and paste multi-line content
            input_field.input_widget.focus()
            await pilot.pause()

            paste_text = "\nBeautiful\nWorld"
            paste_event = Paste(text=paste_text)
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should switch to multi-line mode with paste appended
            assert input_field.is_multiline_mode
            expected_text = "Hello\nBeautiful\nWorld"
            assert input_field.textarea_widget.text == expected_text

    @pytest.mark.asyncio
    async def test_multiline_paste_with_empty_initial_text(self) -> None:
        """Multi-line paste with empty initial text should work correctly."""
        from unittest.mock import Mock

        from textual.app import App
        from textual.events import Paste

        class TestApp(App):
            def compose(self):
                yield InputField(placeholder="Test input")

        app = TestApp()
        async with app.run_test() as pilot:
            # Get the input field
            input_field = app.query_one(InputField)

            # Mock the screen.query_one method
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Start with empty text (cursor at position 0)
            assert input_field.input_widget.value == ""
            assert input_field.input_widget.cursor_position == 0

            # Focus and paste multi-line content
            input_field.input_widget.focus()
            await pilot.pause()

            paste_text = "Line 1\nLine 2\nLine 3"
            paste_event = Paste(text=paste_text)
            input_field.input_widget.post_message(paste_event)
            await pilot.pause()

            # Should switch to multi-line mode with just the pasted content
            assert input_field.is_multiline_mode
            assert input_field.textarea_widget.text == paste_text
