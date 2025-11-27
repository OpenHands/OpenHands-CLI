"""Tests for the textual app functionality."""

import asyncio
import unittest.mock as mock

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Input, Static

from openhands_cli.refactor.textual_app import OpenHandsApp


class TestOpenHandsApp:
    """Tests for the OpenHandsApp class."""

    def test_app_initialization(self):
        """Test that the app initializes correctly."""
        app = OpenHandsApp()
        assert isinstance(app, OpenHandsApp)
        assert hasattr(app, "CSS")
        assert isinstance(app.CSS, str)

    def test_css_contains_required_styles(self):
        """Test that CSS contains all required style definitions."""
        app = OpenHandsApp()
        css = app.CSS

        # Check for main layout styles
        assert "Screen" in css
        assert "layout: vertical" in css

        # Check for main display styles
        assert "#main_display" in css
        assert "height: 1fr" in css

        # Check for input area styles
        assert "#input_area" in css
        assert "dock: bottom" in css

        # Check for user input styles
        assert "#user_input" in css
        assert "border: solid" in css

    @mock.patch("openhands_cli.refactor.textual_app.get_welcome_message")
    async def test_compose_creates_correct_widgets(self, mock_welcome):
        """Test that compose method creates the correct widgets."""
        mock_welcome.return_value = "Test welcome message"

        app = OpenHandsApp()
        async with app.run_test() as pilot:
            # Check that main display exists and is a VerticalScroll
            main_display = pilot.app.query_one("#main_display", VerticalScroll)
            assert isinstance(main_display, VerticalScroll)
            assert main_display.id == "main_display"

            # Check that input area exists
            input_area = pilot.app.query_one("#input_area")
            assert input_area.id == "input_area"

            # Check that user input exists
            user_input = pilot.app.query_one("#user_input", Input)
            assert isinstance(user_input, Input)
            assert user_input.id == "user_input"

    @mock.patch("openhands_cli.refactor.textual_app.get_welcome_message")
    async def test_on_mount_adds_welcome_message(self, mock_welcome):
        """Test that on_mount adds welcome message to display."""
        from openhands_cli.refactor.theme import OPENHANDS_THEME

        welcome_text = "Test welcome message"
        mock_welcome.return_value = welcome_text

        app = OpenHandsApp()
        async with app.run_test() as pilot:
            # Verify welcome message was called with theme
            mock_welcome.assert_called_once_with(theme=OPENHANDS_THEME)

            # Verify main display exists (welcome message should be added during mount)
            main_display = pilot.app.query_one("#main_display", VerticalScroll)
            assert main_display is not None

            # Verify input exists and has focus
            user_input = pilot.app.query_one("#user_input", Input)
            assert user_input is not None

    def test_on_input_submitted_handles_empty_input(self):
        """Test that empty input is ignored."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Create mock event with empty input
        mock_event = mock.MagicMock()
        mock_event.value = ""
        mock_event.input.value = ""

        # Call the method
        app.on_input_submitted(mock_event)

        # mount should not be called for empty input
        mock_main_display.mount.assert_not_called()

        # Input value should not be cleared
        assert mock_event.input.value == ""

    def test_on_input_submitted_handles_whitespace_only_input(self):
        """Test that whitespace-only input is ignored."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Create mock event with whitespace-only input
        mock_event = mock.MagicMock()
        mock_event.value = "   \t\n  "
        mock_event.input.value = "   \t\n  "

        # Call the method
        app.on_input_submitted(mock_event)

        # mount should not be called for whitespace-only input
        mock_main_display.mount.assert_not_called()

        # Input value should not be cleared
        assert mock_event.input.value == "   \t\n  "

    @pytest.mark.parametrize(
        "user_input",
        [
            "hello world",
            "test message",
            "multi\nline\ninput",
            "special chars: !@#$%^&*()",
            "unicode: 🚀 ✨ 🎉",
        ],
    )
    def test_on_input_submitted_handles_valid_input(self, user_input):
        """Test that valid input is processed correctly."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Mock the conversation runner
        mock_conversation_runner = mock.MagicMock()
        mock_conversation_runner.is_running = False
        app.conversation_runner = mock_conversation_runner

        # Create mock event with valid input
        mock_event = mock.MagicMock()
        mock_event.value = user_input
        mock_event.input.value = user_input

        # Call the method
        app.on_input_submitted(mock_event)

        # mount should be called three times:
        # user message + processing + placeholder
        assert mock_main_display.mount.call_count == 3

        # First call should be the user message widget
        first_call_widget = mock_main_display.mount.call_args_list[0][0][0]
        # The widget should be a Static widget with user-message class
        assert first_call_widget.__class__.__name__ == "Static"
        assert "user-message" in first_call_widget.classes
        # The widget content should contain the user input
        assert user_input in str(first_call_widget.content)

        # Second call should be the processing message widget
        second_call_widget = mock_main_display.mount.call_args_list[1][0][0]
        assert "Processing message" in str(second_call_widget.content)

        # Third call should be the placeholder message widget
        third_call_widget = mock_main_display.mount.call_args_list[2][0][0]
        assert "conversation runner" in str(third_call_widget.content)

        # Input value should be cleared
        assert mock_event.input.value == ""

    def test_on_input_submitted_message_format(self):
        """Test that input messages are formatted correctly."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Mock the conversation runner
        mock_conversation_runner = mock.MagicMock()
        mock_conversation_runner.is_running = False
        app.conversation_runner = mock_conversation_runner

        # Create mock event
        mock_event = mock.MagicMock()
        mock_event.value = "test message"
        mock_event.input.value = "test message"

        # Call the method
        app.on_input_submitted(mock_event)

        # Check the exact format of the first message (user input)
        first_call_widget = mock_main_display.mount.call_args_list[0][0][0]
        widget_content = str(first_call_widget.content)
        assert widget_content == "> test message"
        assert widget_content.startswith("> ")

    @mock.patch("openhands_cli.refactor.textual_app.get_welcome_message")
    @mock.patch("openhands_cli.refactor.textual_app.MinimalConversationRunner")
    async def test_input_functionality_integration(
        self, mock_runner_class, mock_welcome
    ):
        """Test that input functionality works end-to-end."""
        mock_welcome.return_value = "Welcome!"

        # Mock the conversation runner to avoid actual API calls
        mock_runner = mock.MagicMock()
        mock_runner.is_running = False

        # Make process_message_async return an async function
        async def mock_process_message_async(message):
            pass

        mock_runner.process_message_async = mock_process_message_async
        mock_runner_class.return_value = mock_runner

        app = OpenHandsApp()
        async with app.run_test() as pilot:
            # Type a message (avoid words that trigger autocomplete)
            await pilot.press("t", "e", "s", "t")

            # Get the input widget
            user_input = pilot.app.query_one("#user_input", Input)
            assert user_input.value == "test"

            # Submit the input
            await pilot.press("enter")

            # Input should be cleared after submission
            assert user_input.value == ""

            # Check that message was added to the display
            # The VerticalScroll should contain both welcome message and user input
            # We can't easily check the exact content, but we can verify it exists
            pilot.app.query_one("#main_display", VerticalScroll)

    @mock.patch("openhands_cli.refactor.textual_app.get_welcome_message")
    async def test_welcome_message_called_on_mount(self, mock_welcome):
        """Test that get_welcome_message is called during on_mount."""
        from openhands_cli.refactor.theme import OPENHANDS_THEME

        mock_welcome.return_value = "Test message"

        app = OpenHandsApp()
        async with app.run_test():
            # Verify get_welcome_message was called with theme during app initialization
            mock_welcome.assert_called_once_with(theme=OPENHANDS_THEME)

    @mock.patch("openhands_cli.refactor.textual_app.get_welcome_message")
    async def test_widget_ids_are_set_correctly(self, mock_welcome):
        """Test that widgets have correct IDs set."""
        mock_welcome.return_value = "test"

        app = OpenHandsApp()
        async with app.run_test() as pilot:
            # Check main display ID
            main_display = pilot.app.query_one("#main_display")
            assert main_display.id == "main_display"

            # Check input area ID
            input_area = pilot.app.query_one("#input_area")
            assert input_area.id == "input_area"

            # Check user input ID
            user_input = pilot.app.query_one("#user_input")
            assert user_input.id == "user_input"

    @mock.patch("openhands_cli.refactor.textual_app.get_welcome_message")
    async def test_main_display_configuration(self, mock_welcome):
        """Test that main display is configured correctly."""
        mock_welcome.return_value = "test"

        app = OpenHandsApp()
        async with app.run_test() as pilot:
            main_display = pilot.app.query_one("#main_display", VerticalScroll)

            # Check VerticalScroll configuration
            assert isinstance(main_display, VerticalScroll)
            assert main_display.id == "main_display"

    def test_custom_theme_properties(self):
        """Test that custom OpenHands theme has correct colors."""
        from openhands_cli.refactor.theme import OPENHANDS_THEME

        # Check theme has correct properties
        assert OPENHANDS_THEME.name == "openhands"
        assert OPENHANDS_THEME.primary == "#ffe165"  # Logo, cursor color
        assert OPENHANDS_THEME.secondary == "#ffffff"  # Borders, plain text
        assert OPENHANDS_THEME.accent == "#277dff"  # Special text
        assert OPENHANDS_THEME.foreground == "#ffffff"  # Default text color
        assert OPENHANDS_THEME.background == "#222222"  # Background color
        assert OPENHANDS_THEME.dark is True

        # Check custom variables
        assert "input-placeholder-foreground" in OPENHANDS_THEME.variables
        assert OPENHANDS_THEME.variables["input-placeholder-foreground"] == "#727987"
        assert OPENHANDS_THEME.variables["input-selection-background"] == "#ffe165 20%"

    def test_theme_registration_and_activation(self):
        """Test that theme is registered and set as active."""
        app = OpenHandsApp()

        # Check that theme is set as active
        assert app.theme == "openhands"

    def test_cursor_css_styling(self):
        """Test that CSS includes cursor styling."""
        app = OpenHandsApp()

        # Check that CSS includes cursor styling
        assert "Input .input--cursor" in app.CSS
        assert "background: $primary" in app.CSS
        assert "color: $background" in app.CSS


class TestStatusLineIndicator:
    """Tests for the status line message indicator functionality."""

    @mock.patch("openhands_cli.refactor.textual_app.get_welcome_message")
    async def test_status_line_widget_creation(self, mock_welcome):
        """Test that status line widget is created with correct styling."""
        mock_welcome.return_value = "Welcome!"

        app = OpenHandsApp()

        # Check CSS includes status line styling
        assert "#status_line" in app.CSS
        assert "dock: bottom" in app.CSS

        async with app.run_test() as pilot:
            status_line = pilot.app.query_one("#status_line", Static)
            assert isinstance(status_line, Static)
            assert status_line.id == "status_line"

    @pytest.mark.parametrize(
        "work_dir,home_dir,expected",
        [
            ("/home/user/project", "/home/user", "~/project"),
            ("/tmp/project", "/home/user", "/tmp/project"),
            ("/home/user/very/long/path", "/home/user", "~/very/long/path"),
        ],
    )
    @mock.patch("os.path.expanduser")
    def test_get_work_dir_display(self, mock_expanduser, work_dir, home_dir, expected):
        """Test work directory display formatting."""
        mock_expanduser.return_value = home_dir

        with mock.patch("openhands_cli.refactor.textual_app.WORK_DIR", work_dir):
            app = OpenHandsApp()
            result = app.get_work_dir_display()
            assert result == expected

    @pytest.mark.parametrize(
        "runner_exists,is_running,has_start_time,expected_contains",
        [
            (False, False, False, ["/test"]),  # No runner - just work dir
            (True, False, False, ["/test"]),  # Runner not running - just work dir
            (True, True, False, ["/test"]),  # Running but no start time - just work dir
            (
                True,
                True,
                True,
                ["/test", "esc to cancel", "Ctrl-E to show details", "s"],
            ),  # Full display
        ],
    )
    @mock.patch("time.time", return_value=1045.0)
    def test_status_line_display_states(
        self, mock_time, runner_exists, is_running, has_start_time, expected_contains
    ):
        """Test status line display in different conversation states."""
        app = OpenHandsApp()

        mock_status_widget = mock.MagicMock(spec=Static)
        app.query_one = mock.MagicMock(return_value=mock_status_widget)

        # Set up conversation state
        if runner_exists:
            mock_runner = mock.MagicMock()
            mock_runner.is_running = is_running
            app.conversation_runner = mock_runner
        else:
            app.conversation_runner = None

        app.conversation_start_time = 1000.0 if has_start_time else None

        with mock.patch.object(app, "get_work_dir_display", return_value="/test"):
            app.update_status_line()

            call_args = mock_status_widget.update.call_args[0][0]
            for expected in expected_contains:
                assert expected in call_args

    @pytest.mark.parametrize(
        "start_time,current_time,expected_duration",
        [
            (1000.0, 1001.0, "1s"),
            (1000.0, 1010.0, "10s"),
            (1000.0, 1060.0, "60s"),
            (1000.0, 1125.0, "125s"),
        ],
    )
    @mock.patch("time.time")
    def test_timer_duration_formatting(
        self, mock_time, start_time, current_time, expected_duration
    ):
        """Test timer displays correct elapsed time."""
        app = OpenHandsApp()

        mock_status_widget = mock.MagicMock(spec=Static)
        app.query_one = mock.MagicMock(return_value=mock_status_widget)

        mock_runner = mock.MagicMock()
        mock_runner.is_running = True
        app.conversation_runner = mock_runner
        app.conversation_start_time = start_time
        mock_time.return_value = current_time

        with mock.patch.object(app, "get_work_dir_display", return_value="/test"):
            app.update_status_line()

            call_args = mock_status_widget.update.call_args[0][0]
            assert expected_duration in call_args

    async def test_timer_lifecycle(self):
        """Test timer start/stop functionality."""
        app = OpenHandsApp()

        # Mock timer and update method
        mock_timer = mock.MagicMock()
        app.set_interval = mock.MagicMock(return_value=mock_timer)
        app.update_status_line = mock.MagicMock()

        # Test start timer
        with mock.patch("time.time", return_value=1000.0):
            await app.start_timer()

        assert app.conversation_start_time == 1000.0
        assert app.timer_update_task == mock_timer
        app.set_interval.assert_called_once_with(1.0, app.update_status_line)

        # Test stop timer
        app.stop_timer()

        mock_timer.stop.assert_called_once()
        assert app.timer_update_task is None
        assert app.conversation_start_time is None
        app.update_status_line.assert_called_once()


class TestPauseFunctionality:
    """Tests for the pause conversation functionality."""

    @mock.patch("asyncio.create_task")
    def test_action_pause_conversation_when_running(self, mock_create_task):
        """Test that pause action works when conversation is running."""
        app = OpenHandsApp()

        # Mock the conversation runner
        mock_runner = mock.MagicMock()
        mock_runner.is_running = True
        app.conversation_runner = mock_runner

        # Mock the main display
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Call the pause action
        app.action_pause_conversation()

        # Verify status message was added immediately
        mock_main_display.mount.assert_called_once()
        pause_widget = mock_main_display.mount.call_args[0][0]
        assert "Pausing conversation" in str(pause_widget.content)
        assert "status-message" in pause_widget.classes

        # Verify asyncio.create_task was called with the async pause function
        mock_create_task.assert_called_once()
        # The argument should be a coroutine from calling
        # app._pause_conversation_async()
        args = mock_create_task.call_args[0]
        assert len(args) == 1
        # We can't easily test the coroutine content, but we can verify it was called

    @mock.patch("asyncio.to_thread")
    async def test_pause_conversation_async_success(self, mock_to_thread):
        """Test the async pause conversation method when successful."""
        app = OpenHandsApp()

        # Mock the conversation runner
        mock_runner = mock.MagicMock()
        mock_runner.is_running = True
        app.conversation_runner = mock_runner

        # Mock asyncio.to_thread to return a completed future
        mock_to_thread.return_value = asyncio.Future()
        mock_to_thread.return_value.set_result(None)

        # Mock the update status method
        app._update_pause_status = mock.MagicMock()

        # Call the async pause method
        await app._pause_conversation_async()

        # Verify asyncio.to_thread was called with the pause method
        mock_to_thread.assert_called_once_with(mock_runner.pause)

        # Verify success status was updated
        app._update_pause_status.assert_called_once_with("Conversation paused.")

    @mock.patch("asyncio.to_thread")
    async def test_pause_conversation_async_failure(self, mock_to_thread):
        """Test the async pause conversation method when it fails."""
        app = OpenHandsApp()

        # Mock the conversation runner
        mock_runner = mock.MagicMock()
        mock_runner.is_running = True
        app.conversation_runner = mock_runner

        # Mock asyncio.to_thread to raise an exception
        mock_to_thread.side_effect = Exception("Network error")

        # Mock the update status method
        app._update_pause_status = mock.MagicMock()

        # Call the async pause method
        await app._pause_conversation_async()

        # Verify asyncio.to_thread was called with the pause method
        mock_to_thread.assert_called_once_with(mock_runner.pause)

        # Verify error status was updated
        app._update_pause_status.assert_called_once_with(
            "Failed to pause: Network error"
        )

    def test_update_pause_status_success(self):
        """Test updating pause status with success message."""
        app = OpenHandsApp()

        # Mock the main display
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Call update with success message
        app._update_pause_status("Conversation paused.")

        # Verify status widget was mounted
        mock_main_display.mount.assert_called_once()
        status_widget = mock_main_display.mount.call_args[0][0]
        assert "[green]Conversation paused.[/green]" in str(status_widget.content)
        assert "status-message" in status_widget.classes

    def test_update_pause_status_failure(self):
        """Test updating pause status with failure message."""
        app = OpenHandsApp()

        # Mock the main display
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Call update with failure message
        app._update_pause_status("Failed to pause: Network error")

        # Verify status widget was mounted
        mock_main_display.mount.assert_called_once()
        status_widget = mock_main_display.mount.call_args[0][0]
        assert "[red]Failed to pause: Network error[/red]" in str(status_widget.content)
        assert "status-message" in status_widget.classes

    @mock.patch("asyncio.create_task")
    def test_action_pause_conversation_when_not_running(self, mock_create_task):
        """Test that pause action does nothing when conversation is not running."""
        app = OpenHandsApp()

        # Mock the conversation runner as not running
        mock_runner = mock.MagicMock()
        mock_runner.is_running = False
        app.conversation_runner = mock_runner

        # Mock the main display
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Call the pause action
        app.action_pause_conversation()

        # Verify no status message was added
        mock_main_display.mount.assert_not_called()

        # Verify asyncio.create_task was not called
        mock_create_task.assert_not_called()

    @mock.patch("asyncio.create_task")
    def test_action_pause_conversation_when_no_runner(self, mock_create_task):
        """Test that pause action does nothing when no conversation runner exists."""
        app = OpenHandsApp()

        # No conversation runner
        app.conversation_runner = None

        # Mock the main display
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Call the pause action
        app.action_pause_conversation()

        # Verify no status message was added
        mock_main_display.mount.assert_not_called()

        # Verify asyncio.create_task was not called
        mock_create_task.assert_not_called()

    def test_escape_key_binding_exists(self):
        """Test that escape key binding is properly configured."""
        app = OpenHandsApp()

        # Check that escape key binding exists in BINDINGS
        escape_binding = ("escape", "pause_conversation", "Pause")
        assert escape_binding in app.BINDINGS


class TestCommandsAndAutocomplete:
    """Tests for command handling and autocomplete functionality."""
