"""Tests for the textual app functionality."""

import unittest.mock as mock

import pytest
from textual.widgets import Input, RichLog
from textual_autocomplete import AutoComplete

from openhands_cli.refactor.textual_app import COMMANDS, OpenHandsApp


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
        assert "overflow-y: scroll" in css

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
            # Check that main display exists and is a RichLog
            main_display = pilot.app.query_one("#main_display", RichLog)
            assert isinstance(main_display, RichLog)
            assert main_display.id == "main_display"
            assert main_display.highlight is False
            assert main_display.markup is True
            assert main_display.can_focus is False

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
            main_display = pilot.app.query_one("#main_display", RichLog)
            assert main_display is not None

            # Verify input exists and has focus
            user_input = pilot.app.query_one("#user_input", Input)
            assert user_input is not None

    def test_on_input_submitted_handles_empty_input(self):
        """Test that empty input is ignored."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_richlog = mock.MagicMock(spec=RichLog)
        app.query_one = mock.MagicMock(return_value=mock_richlog)

        # Create mock event with empty input
        mock_event = mock.MagicMock()
        mock_event.value = ""
        mock_event.input.value = ""

        # Call the method
        app.on_input_submitted(mock_event)

        # RichLog.write should not be called for empty input
        mock_richlog.write.assert_not_called()

        # Input value should not be cleared
        assert mock_event.input.value == ""

    def test_on_input_submitted_handles_whitespace_only_input(self):
        """Test that whitespace-only input is ignored."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_richlog = mock.MagicMock(spec=RichLog)
        app.query_one = mock.MagicMock(return_value=mock_richlog)

        # Create mock event with whitespace-only input
        mock_event = mock.MagicMock()
        mock_event.value = "   \t\n  "
        mock_event.input.value = "   \t\n  "

        # Call the method
        app.on_input_submitted(mock_event)

        # RichLog.write should not be called for whitespace-only input
        mock_richlog.write.assert_not_called()

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
        mock_richlog = mock.MagicMock(spec=RichLog)
        app.query_one = mock.MagicMock(return_value=mock_richlog)

        # Create mock event with valid input
        mock_event = mock.MagicMock()
        mock_event.value = user_input
        mock_event.input.value = user_input

        # Call the method
        app.on_input_submitted(mock_event)

        # RichLog.write should be called twice: user message + placeholder
        assert mock_richlog.write.call_count == 2

        # First call should be the user message
        expected_message = f"\n> {user_input}"
        first_call = mock_richlog.write.call_args_list[0][0][0]
        assert first_call == expected_message

        # Second call should be the placeholder message
        second_call = mock_richlog.write.call_args_list[1][0][0]
        assert "not implemented yet" in second_call

        # Input value should be cleared
        assert mock_event.input.value == ""

    def test_on_input_submitted_message_format(self):
        """Test that input messages are formatted correctly."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_richlog = mock.MagicMock(spec=RichLog)
        app.query_one = mock.MagicMock(return_value=mock_richlog)

        # Create mock event
        mock_event = mock.MagicMock()
        mock_event.value = "test message"
        mock_event.input.value = "test message"

        # Call the method
        app.on_input_submitted(mock_event)

        # Check the exact format of the first message (user input)
        first_call = mock_richlog.write.call_args_list[0][0][0]
        assert first_call == "\n> test message"
        assert first_call.startswith("\n> ")

    @mock.patch("openhands_cli.refactor.textual_app.get_welcome_message")
    async def test_input_functionality_integration(self, mock_welcome):
        """Test that input functionality works end-to-end."""
        mock_welcome.return_value = "Welcome!"

        app = OpenHandsApp()
        async with app.run_test() as pilot:
            # Type a message
            await pilot.press("h", "e", "l", "l", "o")

            # Get the input widget
            user_input = pilot.app.query_one("#user_input", Input)
            assert user_input.value == "hello"

            # Submit the input
            await pilot.press("enter")

            # Input should be cleared after submission
            assert user_input.value == ""

            # Check that message was added to the display
            # The RichLog should contain both welcome message and user input
            # We can't easily check the exact content, but we can verify it exists
            pilot.app.query_one("#main_display", RichLog)

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
    async def test_richlog_configuration(self, mock_welcome):
        """Test that RichLog is configured correctly."""
        mock_welcome.return_value = "test"

        app = OpenHandsApp()
        async with app.run_test() as pilot:
            main_display = pilot.app.query_one("#main_display", RichLog)

            # Check RichLog configuration
            assert isinstance(main_display, RichLog)
            assert main_display.highlight is False
            assert main_display.markup is True
            assert main_display.can_focus is False

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


class TestCommandsAndAutocomplete:
    """Tests for command handling and autocomplete functionality."""

    def test_commands_list_exists(self):
        """Test that COMMANDS list is defined with correct structure."""
        assert isinstance(COMMANDS, list)
        assert len(COMMANDS) == 2

        # Check command names
        command_names = [str(cmd.main) for cmd in COMMANDS]
        assert "/help" in command_names
        assert "/exit" in command_names

    @mock.patch("openhands_cli.refactor.textual_app.get_welcome_message")
    async def test_autocomplete_widget_exists(self, mock_welcome):
        """Test that AutoComplete widget is created."""
        mock_welcome.return_value = "test"

        app = OpenHandsApp()
        async with app.run_test() as pilot:
            # Check that AutoComplete widget exists
            autocomplete = pilot.app.query_one(AutoComplete)
            assert isinstance(autocomplete, AutoComplete)

    def test_handle_command_help(self):
        """Test that /help command displays help information."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_richlog = mock.MagicMock(spec=RichLog)
        app.query_one = mock.MagicMock(return_value=mock_richlog)

        # Call the command handler
        app._handle_command("/help")

        # Check that help text was written
        mock_richlog.write.assert_called_once()
        help_text = mock_richlog.write.call_args[0][0]
        assert "OpenHands CLI Help" in help_text
        assert "/help" in help_text
        assert "/exit" in help_text

    def test_handle_command_exit(self):
        """Test that /exit command exits the app."""
        app = OpenHandsApp()

        # Mock the query_one method and exit method
        mock_richlog = mock.MagicMock(spec=RichLog)
        app.query_one = mock.MagicMock(return_value=mock_richlog)
        app.exit = mock.MagicMock()

        # Call the command handler
        app._handle_command("/exit")

        # Check that goodbye message was written and app exits
        mock_richlog.write.assert_called_once()
        goodbye_text = mock_richlog.write.call_args[0][0]
        assert "Goodbye!" in goodbye_text
        app.exit.assert_called_once()

    def test_handle_command_unknown(self):
        """Test that unknown commands show error message."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_richlog = mock.MagicMock(spec=RichLog)
        app.query_one = mock.MagicMock(return_value=mock_richlog)

        # Call the command handler with unknown command
        app._handle_command("/unknown")

        # Check that error message was written
        mock_richlog.write.assert_called_once_with("Unknown command: /unknown")

    def test_on_input_submitted_handles_commands(self):
        """Test that commands are routed to command handler."""
        app = OpenHandsApp()

        # Mock the query_one method and command handler
        mock_richlog = mock.MagicMock(spec=RichLog)
        app.query_one = mock.MagicMock(return_value=mock_richlog)
        app._handle_command = mock.MagicMock()

        # Create mock event with command input
        mock_event = mock.MagicMock()
        mock_event.value = "/help"
        mock_event.input.value = "/help"

        # Call the method
        app.on_input_submitted(mock_event)

        # Check that command handler was called
        app._handle_command.assert_called_once_with("/help")

        # Input should be cleared
        assert mock_event.input.value == ""

    def test_on_input_submitted_handles_regular_messages(self):
        """Test that non-command messages are handled appropriately."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_richlog = mock.MagicMock(spec=RichLog)
        app.query_one = mock.MagicMock(return_value=mock_richlog)

        # Create mock event with regular message
        mock_event = mock.MagicMock()
        mock_event.value = "hello world"
        mock_event.input.value = "hello world"

        # Call the method
        app.on_input_submitted(mock_event)

        # Check that both user message and placeholder response were written
        assert mock_richlog.write.call_count == 2

        # First call should be the user message
        first_call = mock_richlog.write.call_args_list[0][0][0]
        assert first_call == "\n> hello world"

        # Second call should be the placeholder message
        second_call = mock_richlog.write.call_args_list[1][0][0]
        assert "not implemented yet" in second_call

        # Input should be cleared
        assert mock_event.input.value == ""

    def test_show_help_content(self):
        """Test that help content contains expected information."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_richlog = mock.MagicMock(spec=RichLog)
        app.query_one = mock.MagicMock(return_value=mock_richlog)

        # Call the help method
        app._show_help()

        # Check help content
        help_text = mock_richlog.write.call_args[0][0]
        assert "OpenHands CLI Help" in help_text
        assert "/help" in help_text
        assert "/exit" in help_text
        assert "Display available commands" in help_text
        assert "Exit the application" in help_text
        assert "Tips:" in help_text
        assert "Type / and press Tab" in help_text
