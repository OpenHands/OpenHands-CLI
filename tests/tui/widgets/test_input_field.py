"""Tests for InputField widget component."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from textual.app import App
from textual.events import Paste
from textual.widgets import TextArea

from openhands_cli.tui.widgets.input_field import (
    InputField,
    PasteAwareInput,
    get_external_editor,
)


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


class TestInputFieldExternalEditor:
    """Test external editor functionality."""

    @pytest.mark.asyncio
    async def test_set_content_only_single_line_in_single_mode(self) -> None:
        """Setting single-line content when already in single-line mode."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Mock the screen for toggle functionality
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Ensure we're in single-line mode
            assert not input_field.is_multiline_mode

            # Set single-line content
            content = "Single line content"
            input_field._set_content_only(content)
            await pilot.pause()

            # Should stay in single-line mode
            assert not input_field.is_multiline_mode
            assert input_field.input_widget.value == content
            assert input_field.get_current_value() == content

    @pytest.mark.asyncio
    async def test_set_content_only_single_line_in_multiline_mode(self) -> None:
        """Setting single-line content when in multiline mode should toggle."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Mock the screen for toggle functionality
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Switch to multiline mode first
            input_field.action_toggle_input_mode()
            await pilot.pause()
            assert input_field.is_multiline_mode

            # Set single-line content
            content = "Single line content"
            input_field._set_content_only(content)
            await pilot.pause()

            # Should toggle back to single-line mode
            assert not input_field.is_multiline_mode
            assert input_field.input_widget.value == content
            assert input_field.get_current_value() == content

    @pytest.mark.asyncio
    async def test_set_content_only_multiline_in_single_mode(self) -> None:
        """Setting multiline content when in single-line mode should toggle."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Mock the screen for toggle functionality
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Ensure we're in single-line mode
            assert not input_field.is_multiline_mode

            # Set multiline content
            content = "Line 1\nLine 2\nLine 3"
            input_field._set_content_only(content)
            await pilot.pause()

            # Should toggle to multiline mode
            assert input_field.is_multiline_mode
            assert input_field.textarea_widget.text == content
            assert input_field.get_current_value() == content

    @pytest.mark.asyncio
    async def test_set_content_only_multiline_in_multiline_mode(self) -> None:
        """Setting multiline content when already in multiline mode."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Mock the screen for toggle functionality
            mock_input_area = Mock()
            mock_input_area.styles = Mock()
            input_field.screen.query_one = Mock(return_value=mock_input_area)

            # Switch to multiline mode first
            input_field.action_toggle_input_mode()
            await pilot.pause()
            assert input_field.is_multiline_mode

            # Set multiline content
            content = "Line 1\nLine 2\nLine 3"
            input_field._set_content_only(content)
            await pilot.pause()

            # Should stay in multiline mode
            assert input_field.is_multiline_mode
            assert input_field.textarea_widget.text == content
            assert input_field.get_current_value() == content

    @patch("openhands_cli.tui.widgets.input_field.get_external_editor")
    @patch("tempfile.NamedTemporaryFile")
    @patch("subprocess.run")
    @patch("builtins.open")
    @patch("pathlib.Path.unlink")
    def test_action_open_external_editor_success(
        self,
        mock_unlink,
        mock_open,
        mock_subprocess,
        mock_tempfile,
        mock_get_editor,
        field_with_mocks,
    ) -> None:
        """Test successful external editor workflow."""
        # Setup mocks
        mock_get_editor.return_value = "nano"

        # Mock the temporary file context manager
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test_file"
        mock_temp_file.write = Mock()
        mock_tempfile.return_value.__enter__.return_value = mock_temp_file
        mock_tempfile.return_value.__exit__.return_value = None

        # Mock subprocess
        mock_subprocess.return_value.returncode = 0

        # Mock file reading
        mock_file = Mock()
        mock_file.read.return_value = "Edited content from external editor"
        mock_open.return_value.__enter__.return_value = mock_file
        mock_open.return_value.__exit__.return_value = None

        # Mock app and methods
        mock_app = Mock()
        mock_suspend_context = Mock()
        mock_suspend_context.__enter__ = Mock()
        mock_suspend_context.__exit__ = Mock(return_value=None)
        mock_app.suspend.return_value = mock_suspend_context
        field_with_mocks.get_current_value = Mock(return_value="Initial content")
        field_with_mocks._set_content_only = Mock()

        with patch.object(type(field_with_mocks), "app", new_callable=lambda: mock_app):
            # Call the method
            field_with_mocks.action_open_external_editor()

            # Verify the workflow
            mock_get_editor.assert_called_once()
            mock_tempfile.assert_called_once_with(
                mode="w+", suffix=".txt", delete=False, encoding="utf-8"
            )
            mock_subprocess.assert_called_once_with(
                ["nano", "/tmp/test_file"], check=True
            )
            field_with_mocks._set_content_only.assert_called_once_with(
                "Edited content from external editor"
            )
            mock_app.notify.assert_called_with(
                "Content updated from editor", severity="information"
            )

    @patch("openhands_cli.tui.widgets.input_field.get_external_editor")
    def test_action_open_external_editor_no_editor_found(
        self, mock_get_editor, field_with_mocks
    ) -> None:
        """Test external editor when no editor is found."""
        # Setup mock to raise RuntimeError
        mock_get_editor.side_effect = RuntimeError("No external editor found")

        # Mock app
        mock_app = Mock()

        with patch.object(type(field_with_mocks), "app", new_callable=lambda: mock_app):
            # Call the method
            field_with_mocks.action_open_external_editor()

            # Verify error handling
            mock_app.notify.assert_called_with(
                "No external editor found", severity="error"
            )

    @patch("openhands_cli.tui.widgets.input_field.get_external_editor")
    @patch("tempfile.NamedTemporaryFile")
    @patch("subprocess.run")
    @patch("builtins.open")
    @patch("pathlib.Path.unlink")
    def test_action_open_external_editor_empty_content(
        self,
        mock_unlink,
        mock_open,
        mock_subprocess,
        mock_tempfile,
        mock_get_editor,
        field_with_mocks,
    ) -> None:
        """Test external editor with empty content returned."""
        # Setup mocks
        mock_get_editor.return_value = "nano"

        # Mock the temporary file context manager
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test_file"
        mock_temp_file.write = Mock()
        mock_tempfile.return_value.__enter__.return_value = mock_temp_file
        mock_tempfile.return_value.__exit__.return_value = None

        # Mock subprocess
        mock_subprocess.return_value.returncode = 0

        # Mock file reading - empty content
        mock_file = Mock()
        mock_file.read.return_value = ""
        mock_open.return_value.__enter__.return_value = mock_file
        mock_open.return_value.__exit__.return_value = None

        # Mock app and methods
        mock_app = Mock()
        mock_suspend_context = Mock()
        mock_suspend_context.__enter__ = Mock()
        mock_suspend_context.__exit__ = Mock(return_value=None)
        mock_app.suspend.return_value = mock_suspend_context
        field_with_mocks.get_current_value = Mock(return_value="Initial content")
        field_with_mocks._set_content_only = Mock()

        with patch.object(type(field_with_mocks), "app", new_callable=lambda: mock_app):
            # Call the method
            field_with_mocks.action_open_external_editor()

            # Verify empty content handling
            field_with_mocks._set_content_only.assert_not_called()
            mock_app.notify.assert_called_with(
                "Editor closed without content", severity="warning"
            )

    @patch("openhands_cli.tui.widgets.input_field.get_external_editor")
    @patch("tempfile.NamedTemporaryFile")
    @patch("subprocess.run")
    @patch("pathlib.Path.unlink")
    def test_action_open_external_editor_subprocess_error(
        self,
        mock_unlink,
        mock_subprocess,
        mock_tempfile,
        mock_get_editor,
        field_with_mocks,
    ) -> None:
        """Test external editor when subprocess fails."""
        # Setup mocks
        mock_get_editor.return_value = "nano"

        # Mock the temporary file context manager
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test_file"
        mock_temp_file.write = Mock()
        mock_tempfile.return_value.__enter__.return_value = mock_temp_file
        mock_tempfile.return_value.__exit__.return_value = None

        # Mock subprocess to fail
        mock_subprocess.side_effect = Exception("Editor failed")

        # Mock app and methods
        mock_app = Mock()
        mock_suspend_context = Mock()
        mock_suspend_context.__enter__ = Mock()
        mock_suspend_context.__exit__ = Mock(return_value=None)
        mock_app.suspend.return_value = mock_suspend_context
        field_with_mocks.get_current_value = Mock(return_value="Initial content")

        with patch.object(type(field_with_mocks), "app", new_callable=lambda: mock_app):
            # Call the method
            field_with_mocks.action_open_external_editor()

            # Verify error handling
            mock_app.notify.assert_called_with(
                "Editor error: Editor failed", severity="error"
            )

    @patch("openhands_cli.tui.widgets.input_field.get_external_editor")
    @patch("tempfile.NamedTemporaryFile")
    @patch("subprocess.run")
    @patch("builtins.open")
    @patch("pathlib.Path.unlink")
    def test_action_open_external_editor_content_unchanged(
        self,
        mock_unlink,
        mock_open,
        mock_subprocess,
        mock_tempfile,
        mock_get_editor,
        field_with_mocks,
    ) -> None:
        """Test external editor when content is unchanged."""
        # Setup mocks
        mock_get_editor.return_value = "nano"
        # Mock the temporary file context manager
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test_file"
        mock_temp_file.write = Mock()
        mock_tempfile.return_value.__enter__.return_value = mock_temp_file
        mock_tempfile.return_value.__exit__.return_value = None
        mock_subprocess.return_value.returncode = 0

        # Mock file reading - same content as initial
        initial_content = "Initial content"
        mock_file = Mock()
        mock_file.read.return_value = initial_content
        mock_open.return_value.__enter__.return_value = mock_file
        mock_open.return_value.__exit__.return_value = None

        # Mock app and methods
        mock_app = Mock()
        mock_suspend_context = Mock()
        mock_suspend_context.__enter__ = Mock()
        mock_suspend_context.__exit__ = Mock(return_value=None)
        mock_app.suspend.return_value = mock_suspend_context
        field_with_mocks.get_current_value = Mock(return_value=initial_content)
        field_with_mocks._set_content_only = Mock()

        with patch.object(type(field_with_mocks), "app", new_callable=lambda: mock_app):
            # Call the method
            field_with_mocks.action_open_external_editor()

            # Verify content is set but no "content changed" notification
            field_with_mocks._set_content_only.assert_called_once_with(initial_content)
            # Should NOT get "content updated" notification since content didn't change
            # Only the initial notifications should be called
            assert mock_app.notify.call_count == 2
            mock_app.notify.assert_any_call(
                "CTRL+X triggered - opening external editor...", severity="information"
            )
            mock_app.notify.assert_any_call("Opening external editor...", timeout=1)


class TestGetExternalEditor:
    """Test the get_external_editor function."""

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_visual_env_var(self, mock_which) -> None:
        """Test that VISUAL environment variable takes precedence."""
        with patch.dict("os.environ", {"VISUAL": "code --wait"}):
            mock_which.return_value = "/usr/bin/code"

            result = get_external_editor()

            assert result == "code --wait"
            mock_which.assert_called_once_with("code")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_editor_env_var(self, mock_which) -> None:
        """Test that EDITOR environment variable is used when VISUAL is not set."""
        with patch.dict("os.environ", {"EDITOR": "vim"}):
            mock_which.return_value = "/usr/bin/vim"

            result = get_external_editor()

            assert result == "vim"
            mock_which.assert_called_once_with("vim")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_visual_takes_precedence_over_editor(
        self, mock_which
    ) -> None:
        """Test that VISUAL takes precedence over EDITOR when both are set."""
        with patch.dict("os.environ", {"VISUAL": "emacs", "EDITOR": "vim"}):
            mock_which.return_value = "/usr/bin/emacs"

            result = get_external_editor()

            assert result == "emacs"
            mock_which.assert_called_once_with("emacs")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_env_var_with_args(self, mock_which) -> None:
        """Test handling of editor commands with arguments."""
        with patch.dict("os.environ", {"VISUAL": "code --wait --new-window"}):
            mock_which.return_value = "/usr/bin/code"

            result = get_external_editor()

            assert result == "code --wait --new-window"
            mock_which.assert_called_once_with("code")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_fallback_nano(self, mock_which) -> None:
        """Test fallback to nano when no environment variables are set."""

        def mock_which_side_effect(cmd):
            return "/usr/bin/nano" if cmd == "nano" else None

        mock_which.side_effect = mock_which_side_effect

        result = get_external_editor()

        assert result == "nano"
        mock_which.assert_any_call("nano")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_fallback_vim(self, mock_which) -> None:
        """Test fallback to vim when nano is not available."""

        def mock_which_side_effect(cmd):
            if cmd == "vim":
                return "/usr/bin/vim"
            return None

        mock_which.side_effect = mock_which_side_effect

        result = get_external_editor()

        assert result == "vim"
        mock_which.assert_any_call("nano")
        mock_which.assert_any_call("vim")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_fallback_emacs(self, mock_which) -> None:
        """Test fallback to emacs when nano and vim are not available."""

        def mock_which_side_effect(cmd):
            if cmd == "emacs":
                return "/usr/bin/emacs"
            return None

        mock_which.side_effect = mock_which_side_effect

        result = get_external_editor()

        assert result == "emacs"
        mock_which.assert_any_call("nano")
        mock_which.assert_any_call("vim")
        mock_which.assert_any_call("emacs")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_fallback_vi(self, mock_which) -> None:
        """Test fallback to vi when nano, vim, and emacs are not available."""

        def mock_which_side_effect(cmd):
            if cmd == "vi":
                return "/usr/bin/vi"
            return None

        mock_which.side_effect = mock_which_side_effect

        result = get_external_editor()

        assert result == "vi"
        mock_which.assert_any_call("nano")
        mock_which.assert_any_call("vim")
        mock_which.assert_any_call("emacs")
        mock_which.assert_any_call("vi")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_no_editor_found(self, mock_which) -> None:
        """Test RuntimeError when no suitable editor is found."""
        mock_which.return_value = None

        with pytest.raises(RuntimeError) as exc_info:
            get_external_editor()

        assert "No suitable editor found" in str(exc_info.value)
        assert "Set VISUAL or EDITOR environment variable" in str(exc_info.value)
        # Should check all fallback editors
        mock_which.assert_any_call("nano")
        mock_which.assert_any_call("vim")
        mock_which.assert_any_call("emacs")
        mock_which.assert_any_call("vi")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_env_var_not_found(self, mock_which) -> None:
        """Test fallback when environment variable points to non-existent editor."""
        with patch.dict("os.environ", {"VISUAL": "nonexistent-editor"}):

            def mock_which_side_effect(cmd):
                if cmd == "nano":
                    return "/usr/bin/nano"
                return None

            mock_which.side_effect = mock_which_side_effect

            result = get_external_editor()

            assert result == "nano"
            mock_which.assert_any_call("nonexistent-editor")
            mock_which.assert_any_call("nano")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_empty_env_var(self, mock_which) -> None:
        """Test that empty environment variables are ignored."""
        with patch.dict("os.environ", {"VISUAL": "", "EDITOR": ""}):

            def mock_which_side_effect(cmd):
                return "/usr/bin/nano" if cmd == "nano" else None

            mock_which.side_effect = mock_which_side_effect

            result = get_external_editor()

            assert result == "nano"
            mock_which.assert_any_call("nano")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which")
    def test_get_external_editor_whitespace_env_var(self, mock_which) -> None:
        """Test that whitespace-only environment variables are ignored."""
        with patch.dict("os.environ", {"VISUAL": "   ", "EDITOR": "\t\n"}):

            def mock_which_side_effect(cmd):
                return "/usr/bin/nano" if cmd == "nano" else None

            mock_which.side_effect = mock_which_side_effect

            result = get_external_editor()

            assert result == "nano"
            mock_which.assert_any_call("nano")
