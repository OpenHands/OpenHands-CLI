"""Tests for InputField widget component."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from textual.app import App
from textual.events import Paste
from textual.widgets import TextArea

from openhands_cli.tui.messages import UserInputSubmitted
from openhands_cli.tui.widgets.user_input.input_field import (
    InputField,
    get_external_editor,
)
from openhands_cli.tui.widgets.user_input.single_line_input import (
    SingleLineInputWithWrapping,
)


@pytest.fixture
def input_field() -> InputField:
    """Create a fresh InputField instance for each test."""
    return InputField(placeholder="Test placeholder")


@pytest.fixture
def field_with_mocks(input_field: InputField) -> Generator[InputField, None, None]:
    """InputField with its internal widgets and signal mocked out."""
    input_field.single_line_widget = MagicMock(spec=SingleLineInputWithWrapping)
    input_field.multiline_widget = MagicMock(spec=TextArea)

    # Set active_input_widget to single_line_widget by default (single-line mode)
    input_field.active_input_widget = input_field.single_line_widget

    # Create separate mock objects for focus methods
    input_focus_mock = MagicMock()
    textarea_focus_mock = MagicMock()
    input_field.single_line_widget.focus = input_focus_mock
    input_field.multiline_widget.focus = textarea_focus_mock

    # Mock document.end for move_cursor calls
    mock_document = MagicMock()
    mock_document.end = (0, 0)
    input_field.single_line_widget.document = mock_document
    input_field.multiline_widget.document = mock_document
    input_field.single_line_widget.move_cursor = MagicMock()
    input_field.multiline_widget.move_cursor = MagicMock()

    # Create mock for the signal and its publish method
    signal_mock = MagicMock()
    publish_mock = MagicMock()
    signal_mock.publish = publish_mock
    input_field.multiline_mode_status = signal_mock

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
        assert hasattr(input_field, "multiline_mode_status")
        # Widgets themselves are created in compose() / on_mount(), so not asserted.

    @pytest.mark.parametrize(
        "content",
        [
            "Simple text",
            "Line 1\nLine 2",
            "Multi\nLine\nText",
            "",
            "\n\n",
        ],
    )
    def test_toggle_input_mode_preserves_content_and_toggles_visibility(
        self,
        field_with_mocks: InputField,
        content: str,
    ) -> None:
        """Toggling mode preserves content and flips displays + signal."""
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
            # Set multiline mode
            field_with_mocks.action_toggle_input_mode()
            assert field_with_mocks.is_multiline_mode is True
            assert field_with_mocks.single_line_widget.display is False
            assert field_with_mocks.multiline_widget.display is True

            # Seed content
            field_with_mocks.multiline_widget.text = content

            field_with_mocks.action_toggle_input_mode()
            field_with_mocks.multiline_mode_status.publish.assert_called()  # type: ignore

            # Multi-line -> single-line: content is preserved as-is (no conversion)
            assert field_with_mocks.single_line_widget.text == content

            # Single-line -> multi-line
            field_with_mocks.action_toggle_input_mode()
            field_with_mocks.multiline_mode_status.publish.assert_called()  # type: ignore

            # Check content is preserved
            assert field_with_mocks.multiline_widget.text == content

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
        """_submit_current_content submits trimmed content only when non-empty."""
        # Set up single line widget as active
        field_with_mocks.active_input_widget = field_with_mocks.single_line_widget
        field_with_mocks.single_line_widget.text = content
        field_with_mocks.post_message = Mock()

        field_with_mocks._submit_current_content()

        if should_submit:
            field_with_mocks.post_message.assert_called_once()
            msg = field_with_mocks.post_message.call_args[0][0]
            assert isinstance(msg, UserInputSubmitted)
            assert msg.content == content.strip()
            # Input cleared after submission
            field_with_mocks.single_line_widget.clear.assert_called_once()  # type: ignore[union-attr]
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
        # Set up multiline widget as active
        field_with_mocks.active_input_widget = field_with_mocks.multiline_widget
        field_with_mocks.multiline_widget.text = content

        field_with_mocks.post_message = Mock()
        field_with_mocks.action_toggle_input_mode = Mock()

        field_with_mocks.action_submit_textarea()

        if should_submit:
            # Textarea cleared
            field_with_mocks.multiline_widget.clear.assert_called_once()  # type: ignore[union-attr]
            # Mode toggle requested
            field_with_mocks.action_toggle_input_mode.assert_called_once()
            # Message posted
            field_with_mocks.post_message.assert_called_once()
            msg = field_with_mocks.post_message.call_args[0][0]
            assert isinstance(msg, UserInputSubmitted)
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
    def test_get_current_text_uses_active_widget(
        self,
        field_with_mocks: InputField,
        is_multiline: bool,
        widget_content: str,
        expected: str,
    ) -> None:
        """_get_current_text() returns content from the active widget."""
        if is_multiline:
            field_with_mocks.active_input_widget = field_with_mocks.multiline_widget
            field_with_mocks.multiline_widget.text = widget_content
        else:
            field_with_mocks.active_input_widget = field_with_mocks.single_line_widget
            field_with_mocks.single_line_widget.text = widget_content

        assert field_with_mocks._get_current_text() == expected

    @pytest.mark.parametrize("is_multiline", [False, True])
    def test_focus_input_focuses_active_widget(
        self,
        field_with_mocks: InputField,
        is_multiline: bool,
    ) -> None:
        """focus_input() focuses the widget corresponding to the current mode."""
        if is_multiline:
            field_with_mocks.active_input_widget = field_with_mocks.multiline_widget
        else:
            field_with_mocks.active_input_widget = field_with_mocks.single_line_widget

        field_with_mocks.focus_input()

        if is_multiline:
            field_with_mocks.multiline_widget.focus.assert_called_once()  # type: ignore
            field_with_mocks.single_line_widget.focus.assert_not_called()  # type: ignore
        else:
            field_with_mocks.single_line_widget.focus.assert_called_once()  # type: ignore
            field_with_mocks.multiline_widget.focus.assert_not_called()  # type: ignore

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
        self, paste_text: str, expected_text: str | None = None
    ) -> None:
        """Shared scenario: multi-line-ish paste should flip to multi-line mode."""
        if expected_text is None:
            expected_text = paste_text

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
            ("Line 1\nLine 2\nLine 3", "Line 1\nLine 2\nLine 3"),  # Unix newlines
            ("Line 1\rLine 2", "Line 1\nLine 2"),  # Classic Mac CR -> normalized to LF
            (
                "Line 1\r\nLine 2\r\nLine 3",
                "Line 1\nLine 2\nLine 3",
            ),  # Windows CRLF -> normalized to LF
        ],
    )
    async def test_multiline_paste_variants_switch_to_multiline_mode(
        self, paste_text: str, expected_text: str
    ) -> None:
        """Any multi-line-ish paste should trigger automatic mode switch."""
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

            # Start in single-line mode with initial text + cursor position
            assert not input_field.is_multiline_mode
            input_field.single_line_widget.text = initial_text
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

            # Paste into single_line_widget (not focused) – should be ignored
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


class TestInputFieldExternalEditor:
    """Test external editor functionality."""

    @pytest.mark.asyncio
    async def test_set_content_in_single_line_mode(self) -> None:
        """Setting content in single-line mode via active_input_widget.text."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Ensure we're in single-line mode
            assert not input_field.is_multiline_mode

            # Set content directly on active widget
            content = "Single line content"
            input_field.active_input_widget.text = content
            await pilot.pause()

            # Should stay in single-line mode
            assert not input_field.is_multiline_mode
            assert input_field.single_line_widget.text == content
            assert input_field._get_current_text() == content

    @pytest.mark.asyncio
    async def test_set_content_in_multiline_mode(self) -> None:
        """Setting content in multiline mode via active_input_widget.text."""
        app = InputFieldTestApp()
        async with app.run_test() as pilot:
            input_field = app.query_one(InputField)

            # Switch to multiline mode first
            input_field.action_toggle_input_mode()
            await pilot.pause()
            assert input_field.is_multiline_mode

            # Set multiline content directly on active widget
            content = "Line 1\nLine 2\nLine 3"
            input_field.active_input_widget.text = content
            await pilot.pause()

            # Should stay in multiline mode
            assert input_field.is_multiline_mode
            assert input_field.multiline_widget.text == content
            assert input_field._get_current_text() == content

    @patch("openhands_cli.tui.widgets.user_input.input_field.get_external_editor")
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
        field_with_mocks.active_input_widget.text = "Initial content"

        # Mock document.end for move_cursor
        mock_document = Mock()
        mock_document.end = (0, 0)
        field_with_mocks.active_input_widget.document = mock_document
        field_with_mocks.active_input_widget.move_cursor = Mock()

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
            # Content is set on active widget
            assert (
                field_with_mocks.active_input_widget.text
                == "Edited content from external editor"
            )
            mock_app.notify.assert_called_with(
                "Content updated from editor", severity="information"
            )

    @patch("openhands_cli.tui.widgets.user_input.input_field.get_external_editor")
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

    @patch("openhands_cli.tui.widgets.user_input.input_field.get_external_editor")
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
        field_with_mocks.active_input_widget.text = "Initial content"

        with patch.object(type(field_with_mocks), "app", new_callable=lambda: mock_app):
            # Call the method
            field_with_mocks.action_open_external_editor()

            # Verify empty content handling - content should not change
            mock_app.notify.assert_called_with(
                "Editor closed without content", severity="warning"
            )

    @patch("openhands_cli.tui.widgets.user_input.input_field.get_external_editor")
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
        field_with_mocks.active_input_widget.text = "Initial content"

        with patch.object(type(field_with_mocks), "app", new_callable=lambda: mock_app):
            # Call the method
            field_with_mocks.action_open_external_editor()

            # Verify error handling
            mock_app.notify.assert_called_with(
                "Editor error: Editor failed", severity="error"
            )

    @patch("openhands_cli.tui.widgets.user_input.input_field.get_external_editor")
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
        field_with_mocks.active_input_widget.text = initial_content

        # Mock document.end for move_cursor
        mock_document = Mock()
        mock_document.end = (0, 0)
        field_with_mocks.active_input_widget.document = mock_document
        field_with_mocks.active_input_widget.move_cursor = Mock()

        with patch.object(type(field_with_mocks), "app", new_callable=lambda: mock_app):
            # Call the method
            field_with_mocks.action_open_external_editor()

            # Content is set but no "content changed" notification since same
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
