"""Tests for autocomplete functionality and command handling."""

from unittest import mock

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Input
from textual_autocomplete import AutoComplete, TargetState

from openhands_cli.refactor.autocomplete import (
    CommandAutoComplete,
    EnhancedAutoComplete,
)
from openhands_cli.refactor.commands import (
    COMMANDS,
    get_valid_commands,
    is_valid_command,
    show_help,
)
from openhands_cli.refactor.textual_app import OpenHandsApp


class TestCommandsAndAutocomplete:
    """Tests for command handling and autocomplete functionality."""

    def test_commands_list_exists(self):
        """Test that COMMANDS list is properly defined."""
        assert isinstance(COMMANDS, list)
        assert len(COMMANDS) > 0

        # Check that all commands are properly formatted
        command_names = [str(cmd.main) for cmd in COMMANDS]
        assert "/help - Display available commands" in command_names
        assert "/exit - Exit the application" in command_names

    async def test_autocomplete_widget_exists(self):
        """Test that CommandAutoComplete widget is created."""
        from openhands_cli.refactor.textual_app import get_welcome_message

        with mock.patch.object(get_welcome_message, "__call__", return_value="test"):
            app = OpenHandsApp()
            async with app.run_test() as pilot:
                # Check that EnhancedAutoComplete widget exists
                autocomplete = pilot.app.query_one(EnhancedAutoComplete)
                assert isinstance(autocomplete, EnhancedAutoComplete)
                assert isinstance(
                    autocomplete, AutoComplete
                )  # Should also be an AutoComplete

    def test_handle_command_help(self):
        """Test that /help command displays help information."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Call the command handler
        app._handle_command("/help")

        # Check that help text was mounted
        mock_main_display.mount.assert_called_once()
        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = str(help_widget.content)
        assert "OpenHands CLI Help" in help_text
        assert "/help" in help_text
        assert "/exit" in help_text

    def test_handle_command_exit_with_confirmation(self):
        """Test that /exit command shows confirmation modal.

        When exit_confirmation=True.
        """
        app = OpenHandsApp(exit_confirmation=True)

        # Mock the query_one method and push_screen method
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)
        app.push_screen = mock.MagicMock()

        # Call the command handler
        app._handle_command("/exit")

        # Check that modal screen was pushed
        app.push_screen.assert_called_once()
        # Verify the argument is an ExitConfirmationModal instance
        modal_arg = app.push_screen.call_args[0][0]
        from openhands_cli.refactor.exit_modal import ExitConfirmationModal

        assert isinstance(modal_arg, ExitConfirmationModal)

    def test_handle_command_exit_without_confirmation(self):
        """Test that /exit command exits immediately when exit_confirmation=False."""
        app = OpenHandsApp(exit_confirmation=False)

        # Mock the query_one method and exit method
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)
        app.exit = mock.MagicMock()

        # Call the command handler
        app._handle_command("/exit")

        # Check that app exits immediately
        app.exit.assert_called_once()

    def test_ctrl_q_binding(self):
        """Test that Ctrl+Q binding triggers exit handling."""
        app = OpenHandsApp(exit_confirmation=True)

        # Mock the push_screen method
        app.push_screen = mock.MagicMock()

        # Call the action directly
        app.action_request_quit()

        # Check that modal screen was pushed
        app.push_screen.assert_called_once()
        modal_arg = app.push_screen.call_args[0][0]
        from openhands_cli.refactor.exit_modal import ExitConfirmationModal

        assert isinstance(modal_arg, ExitConfirmationModal)

    def test_exit_confirmation_modal(self):
        """Test that ExitConfirmationModal works correctly."""
        from textual.containers import Grid

        from openhands_cli.refactor.exit_modal import ExitConfirmationModal

        # Create modal instance
        modal = ExitConfirmationModal()

        # Test compose method
        compose_result = list(modal.compose())
        assert len(compose_result) == 1

        # Check that it has a Grid container
        grid = compose_result[0]
        assert isinstance(grid, Grid)
        assert grid.id == "dialog"

        # Test CSS is defined
        assert hasattr(modal, "DEFAULT_CSS")
        assert "ExitConfirmationModal" in modal.DEFAULT_CSS
        assert "#dialog" in modal.DEFAULT_CSS

    def test_exit_modal_button_handling(self):
        """Test that modal button handling logic is correct."""
        from unittest import mock

        from textual.widgets import Button

        from openhands_cli.refactor.exit_modal import ExitConfirmationModal

        modal = ExitConfirmationModal()

        # Create a mock app and manually set it
        mock_app = mock.MagicMock()

        # Patch the app property to return our mock
        with mock.patch.object(
            type(modal), "app", new_callable=mock.PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            # Test "yes" button - should exit app
            yes_button = Button("Yes", id="yes")
            yes_event = Button.Pressed(yes_button)
            modal.on_button_pressed(yes_event)
            mock_app.exit.assert_called_once()

            # Reset mock
            mock_app.reset_mock()

            # Test "no" button - should pop screen
            no_button = Button("No", id="no")
            no_event = Button.Pressed(no_button)
            modal.on_button_pressed(no_event)
            mock_app.pop_screen.assert_called_once()

    def test_handle_command_unknown(self):
        """Test that unknown commands show error message."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Call the command handler with unknown command
        app._handle_command("/unknown")

        # Check that error message was mounted
        mock_main_display.mount.assert_called_once()
        error_widget = mock_main_display.mount.call_args[0][0]
        error_text = str(error_widget.content)
        assert "Unknown command: /unknown" in error_text

    def test_on_input_submitted_handles_commands(self):
        """Test that commands are routed to command handler."""
        app = OpenHandsApp()

        # Mock the query_one method and command handler
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)
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
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)

        # Mock the conversation runner
        mock_conversation_runner = mock.MagicMock()
        mock_conversation_runner.is_running = False
        app.conversation_runner = mock_conversation_runner

        # Create mock event with regular message
        mock_event = mock.MagicMock()
        mock_event.value = "hello world"
        mock_event.input.value = "hello world"

        # Call the method
        app.on_input_submitted(mock_event)

        # Check that user message, processing message, and placeholder response
        # were mounted
        assert mock_main_display.mount.call_count == 3

        # First call should be the user message widget
        first_call_widget = mock_main_display.mount.call_args_list[0][0][0]
        first_call_text = str(first_call_widget.content)
        assert first_call_text == "> hello world"

        # Second call should be the processing message widget
        second_call_widget = mock_main_display.mount.call_args_list[1][0][0]
        second_call_text = str(second_call_widget.content)
        assert "Processing message" in second_call_text

        # Third call should be the placeholder message widget
        third_call_widget = mock_main_display.mount.call_args_list[2][0][0]
        third_call_text = str(third_call_widget.content)
        assert "conversation runner" in third_call_text

        # Input should be cleared
        assert mock_event.input.value == ""

    def test_show_help_content(self):
        """Test that help content contains expected information."""
        # Mock the VerticalScroll widget
        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        # Call the help function directly
        show_help(mock_main_display)

        # Check help content
        mock_main_display.mount.assert_called_once()
        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = str(help_widget.content)
        assert "OpenHands CLI Help" in help_text
        assert "/help" in help_text
        assert "/exit" in help_text
        assert "Display available commands" in help_text
        assert "Exit the application" in help_text
        assert "Tips:" in help_text
        assert "Type / and press Tab" in help_text

    def test_exact_command_matching_valid_commands(self):
        """Test that exact command matches are treated as commands."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)
        app._handle_command = mock.MagicMock()

        # Test exact command matches
        valid_commands = ["/help", "/exit"]

        for command in valid_commands:
            mock_event = mock.MagicMock()
            mock_event.value = command
            mock_event.input.value = command

            app.on_input_submitted(mock_event)

            # Should call _handle_command for exact matches
            app._handle_command.assert_called_with(command)

            # Reset mock for next iteration
            app._handle_command.reset_mock()

    def test_exact_command_matching_invalid_commands(self):
        """Test that non-exact matches are treated as regular messages."""
        app = OpenHandsApp()

        # Mock the query_one method
        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        app.query_one = mock.MagicMock(return_value=mock_main_display)
        app._handle_command = mock.MagicMock()

        # Test inputs that start with / but are not exact command matches
        invalid_commands = [
            "/help hello",  # Command with extra text
            "/exit now",  # Command with extra text
            "/help-me",  # Command with suffix
            "/unknown",  # Unknown command
            "/",  # Just slash
            "/ help",  # Slash with space
            "/HELP",  # Wrong case
        ]

        for invalid_command in invalid_commands:
            mock_event = mock.MagicMock()
            mock_event.value = invalid_command
            mock_event.input.value = invalid_command

            # Reset mocks
            mock_main_display.reset_mock()
            app._handle_command.reset_mock()

            app.on_input_submitted(mock_event)

            # Should NOT call _handle_command for non-exact matches
            app._handle_command.assert_not_called()

            # Should be treated as regular message instead
            # Check that user message was mounted (first call)
            assert mock_main_display.mount.call_count >= 1
            first_call_widget = mock_main_display.mount.call_args_list[0][0][0]
            first_call_text = str(first_call_widget.content)
            assert first_call_text == f"> {invalid_command}"

    def test_get_valid_commands(self):
        """Test that get_valid_commands extracts command names correctly."""
        valid_commands = get_valid_commands()

        # Should be a set
        assert isinstance(valid_commands, set)

        # Should contain expected commands
        assert "/help" in valid_commands
        assert "/exit" in valid_commands

        # Should have correct count
        assert len(valid_commands) == 2

    def test_is_valid_command(self):
        """Test that is_valid_command correctly identifies valid commands."""
        # Valid commands
        assert is_valid_command("/help") is True
        assert is_valid_command("/exit") is True

        # Invalid commands
        assert is_valid_command("/help hello") is False
        assert is_valid_command("/exit now") is False
        assert is_valid_command("/unknown") is False
        assert is_valid_command("/") is False
        assert is_valid_command("/HELP") is False
        assert is_valid_command("help") is False
        assert is_valid_command("") is False

    @pytest.mark.parametrize(
        "completion_value,expected_command",
        [
            ("/help - Display available commands", "/help"),
            ("/exit - Exit the application", "/exit"),
            ("/help", "/help"),  # No description separator
            ("/exit", "/exit"),  # No description separator
            ("/custom - Some description", "/custom"),
            ("/test", "/test"),  # No separator at all
        ],
    )
    def test_command_autocomplete_apply_completion(
        self, completion_value, expected_command
    ):
        """Test that CommandAutoComplete only completes the command part."""
        # Create a mock input widget
        mock_input = mock.MagicMock(spec=Input)

        # Create CommandAutoComplete instance
        autocomplete = CommandAutoComplete(target=mock_input, candidates=COMMANDS)

        # Create a mock state
        mock_state = TargetState(text="", cursor_position=0)

        # Test completion
        autocomplete.apply_completion(completion_value, mock_state)

        # Should clear value and insert command part
        assert mock_input.value == ""
        mock_input.insert_text_at_cursor.assert_called_with(expected_command)

    @pytest.mark.parametrize(
        "text,cursor_position,expected_search_string",
        [
            # Valid slash commands
            ("/", 1, "/"),
            ("/h", 2, "/h"),
            ("/he", 3, "/he"),
            ("/help", 5, "/help"),
            ("/exit", 5, "/exit"),
            ("/unknown", 8, "/unknown"),
            # Leading whitespace should be ignored
            ("  /help", 7, "/help"),
            ("\t/exit", 6, "/exit"),
            ("   /", 4, "/"),
            # Non-slash commands should return empty string
            ("help", 4, ""),
            ("hello", 5, ""),
            ("", 0, ""),
            ("regular text", 12, ""),
            # Commands with spaces should return empty string (stop matching)
            ("/help ", 6, ""),
            ("/help arg", 9, ""),
            ("/exit now", 9, ""),
            ("/help - Display", 15, ""),
            # Cursor position tests
            ("/help", 0, ""),  # Cursor at start
            ("/help", 1, "/"),  # Cursor after slash
            ("/help", 3, "/he"),  # Cursor in middle
            # Edge cases with whitespace and spaces
            ("  /help ", 8, ""),  # Leading whitespace but has space
            (" ", 1, ""),  # Just whitespace
            ("  ", 2, ""),  # Multiple whitespace
        ],
    )
    def test_command_autocomplete_get_search_string(
        self, text, cursor_position, expected_search_string
    ):
        """Test that get_search_string returns correct search strings."""
        # Create CommandAutoComplete instance with a mock input
        mock_input = mock.MagicMock(spec=Input)
        autocomplete = CommandAutoComplete(target=mock_input, candidates=COMMANDS)

        # Create target state
        target_state = TargetState(text=text, cursor_position=cursor_position)

        # Test search string extraction
        result = autocomplete.get_search_string(target_state)
        assert result == expected_search_string


class TestEnhancedAutoComplete:
    """Tests for the enhanced autocomplete functionality."""

    def test_enhanced_autocomplete_initialization(self):
        """Test that EnhancedAutoComplete initializes correctly."""
        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=COMMANDS)

        assert autocomplete.command_candidates == COMMANDS
        assert isinstance(autocomplete, AutoComplete)

    @pytest.mark.parametrize(
        "text,cursor_position,expected_type",
        [
            # Command completion cases
            ("/", 1, "command"),
            ("/h", 2, "command"),
            ("/help", 5, "command"),
            ("/exit", 5, "command"),
            # File path completion cases - @ at beginning
            ("@", 1, "file"),
            ("@R", 2, "file"),
            ("@README", 7, "file"),
            ("@openhands_cli/", 15, "file"),
            # File path completion cases - @ anywhere in text
            ("read @", 6, "file"),
            ("cat @README", 11, "file"),
            ("edit @src/main.py", 17, "file"),
            ("open @openhands_cli/", 20, "file"),
            # No completion cases
            ("hello", 5, "none"),
            ("", 0, "none"),
            ("regular text", 12, "none"),
        ],
    )
    def test_enhanced_autocomplete_get_candidates_type(
        self, text, cursor_position, expected_type
    ):
        """Test that get_candidates returns appropriate candidate types."""
        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=COMMANDS)

        target_state = TargetState(text=text, cursor_position=cursor_position)
        candidates = autocomplete.get_candidates(target_state)

        if expected_type == "command":
            # Should return command candidates
            assert len(candidates) > 0
            assert all(str(c.main).startswith("/") for c in candidates)
        elif expected_type == "file":
            # Should return file candidates (may be empty if no files match)
            assert isinstance(candidates, list)
            if candidates:  # If there are candidates, they should start with @
                assert all(str(c.main).startswith("@") for c in candidates)
        else:  # expected_type == "none"
            # Should return empty list
            assert candidates == []

    @pytest.mark.parametrize(
        "text,cursor_position,expected_search_string",
        [
            # Command search strings
            ("/", 1, "/"),
            ("/h", 2, "/h"),
            ("/help", 5, "/help"),
            ("/help ", 6, ""),  # Space stops command completion
            # File path search strings - @ at beginning
            ("@", 1, ""),  # Empty filename part
            ("@R", 2, "R"),
            ("@README", 7, "README"),
            ("@openhands_cli/", 15, ""),  # Directory with trailing slash
            ("@openhands_cli/test", 19, "test"),
            ("@path/to/file.py", 16, "file.py"),
            ("@file ", 6, ""),  # Space stops file completion
            # File path search strings - @ anywhere in text
            ("read @", 6, ""),  # Empty filename part
            ("read @R", 7, "R"),
            ("cat @README", 11, "README"),
            ("edit @src/main.py", 17, "main.py"),
            ("open @openhands_cli/", 20, ""),  # Directory with trailing slash
            ("view @file ", 11, ""),  # Space stops file completion
            # No completion cases
            ("hello", 5, ""),
            ("", 0, ""),
        ],
    )
    def test_enhanced_autocomplete_get_search_string(
        self, text, cursor_position, expected_search_string
    ):
        """Test that get_search_string works for both commands and file paths."""
        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=COMMANDS)

        target_state = TargetState(text=text, cursor_position=cursor_position)
        result = autocomplete.get_search_string(target_state)
        assert result == expected_search_string

    def test_enhanced_autocomplete_apply_completion_command(self):
        """Test that apply_completion works correctly for commands."""
        mock_input = mock.MagicMock(spec=Input)
        mock_input.value = "/he"

        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=COMMANDS)

        # Create a mock state
        mock_state = TargetState(text="/he", cursor_position=3)

        # Test command completion
        autocomplete.apply_completion("/help - Display available commands", mock_state)

        # Should clear and insert command only
        assert mock_input.value == ""
        mock_input.insert_text_at_cursor.assert_called_with("/help")

    def test_enhanced_autocomplete_apply_completion_file(self):
        """Test that apply_completion works correctly for file paths."""
        mock_input = mock.MagicMock(spec=Input)
        mock_input.value = "@READ"

        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=COMMANDS)

        # Create a mock state
        mock_state = TargetState(text="@READ", cursor_position=5)

        # Test file path completion
        autocomplete.apply_completion("@README.md", mock_state)

        # Should clear and insert full file path
        assert mock_input.value == ""
        mock_input.insert_text_at_cursor.assert_called_with("@README.md")

    def test_enhanced_autocomplete_apply_completion_file_anywhere(self):
        """Test apply_completion works for file paths anywhere in text."""
        mock_input = mock.MagicMock(spec=Input)
        mock_input.value = "read @READ"

        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=COMMANDS)

        # Create a mock state
        mock_state = TargetState(text="read @READ", cursor_position=10)

        # Test file path completion
        autocomplete.apply_completion("@README.md", mock_state)

        # Should clear and insert prefix + file path
        assert mock_input.value == ""
        mock_input.insert_text_at_cursor.assert_called_with("read @README.md")

    def test_file_candidates_with_real_files(self):
        """Test that file candidates include real files from the working directory."""
        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=COMMANDS)

        # Test getting file candidates for @ (root directory)
        target_state = TargetState(text="@", cursor_position=1)
        candidates = autocomplete.get_candidates(target_state)

        # Should have some candidates (files in the working directory)
        assert isinstance(candidates, list)
        if candidates:  # If there are files in the directory
            # All should start with @
            assert all(str(c.main).startswith("@") for c in candidates)
            # Should have prefixes (file/folder icons)
            assert all(
                hasattr(c, "prefix") and c.prefix in ["📁", "📄"] for c in candidates
            )

    def test_file_candidates_empty_directory(self):
        """Test file candidates behavior with non-existent directory."""
        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=COMMANDS)

        # Test with a path that doesn't exist
        target_state = TargetState(text="@nonexistent/", cursor_position=13)
        candidates = autocomplete.get_candidates(target_state)

        # Should return empty list for non-existent directory
        assert candidates == []

    def test_should_show_dropdown_override_exists(self):
        """Test that should_show_dropdown method is overridden."""
        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=COMMANDS)

        # Verify the method exists and is overridden
        assert hasattr(autocomplete, "should_show_dropdown")
        assert callable(autocomplete.should_show_dropdown)

        # Verify it's our override, not the base class method
        from textual_autocomplete import AutoComplete

        base_method = AutoComplete.should_show_dropdown
        enhanced_method = EnhancedAutoComplete.should_show_dropdown
        assert base_method != enhanced_method
