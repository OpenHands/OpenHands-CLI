"""Tests for the commands module."""

from unittest import mock

import pytest
from textual.containers import VerticalScroll
from textual_autocomplete import DropdownItem

from openhands_cli.refactor.commands import COMMANDS, show_help


class TestCommands:
    """Tests for command definitions and handlers."""

    def test_commands_list_structure(self):
        """Test that COMMANDS list has correct structure."""
        assert isinstance(COMMANDS, list)
        assert len(COMMANDS) == 2

        # Check that all items are DropdownItems
        for command in COMMANDS:
            assert isinstance(command, DropdownItem)
            assert hasattr(command, "main")
            # main is a Content object, not a string
            assert hasattr(command.main, "__str__")

    @pytest.mark.parametrize(
        "expected_command,expected_description",
        [
            ("/help", "Display available commands"),
            ("/exit", "Exit the application"),
        ],
    )
    def test_commands_content(self, expected_command, expected_description):
        """Test that commands contain expected content."""
        command_strings = [str(cmd.main) for cmd in COMMANDS]

        # Find the command that starts with expected_command
        matching_command = None
        for cmd_str in command_strings:
            if cmd_str.startswith(expected_command):
                matching_command = cmd_str
                break

        assert matching_command is not None, f"Command {expected_command} not found"
        assert expected_description in matching_command
        assert " - " in matching_command  # Should have separator

    def test_show_help_function_signature(self):
        """Test that show_help has correct function signature."""
        import inspect

        sig = inspect.signature(show_help)
        params = list(sig.parameters.keys())

        assert len(params) == 1
        assert params[0] == "main_display"

    @pytest.mark.parametrize(
        "expected_content",
        [
            "OpenHands CLI Help",
            "/help",
            "/exit",
            "Display available commands",
            "Exit the application",
            "Tips:",
            "Type / and press Tab",
            "Use arrow keys to navigate",
            "Press Enter to select",
        ],
    )
    def test_show_help_content_elements(self, expected_content):
        """Test that show_help includes all expected content elements."""
        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        show_help(mock_main_display)

        # Get the help text that was mounted
        mock_main_display.mount.assert_called_once()
        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = help_widget.content

        assert expected_content in help_text

    def test_show_help_uses_theme_colors(self):
        """Test that show_help uses OpenHands theme colors."""
        from openhands_cli.refactor.theme import OPENHANDS_THEME

        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        show_help(mock_main_display)

        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = help_widget.content

        # Should use OpenHands theme colors
        assert OPENHANDS_THEME.primary in help_text  # Primary color (yellow)
        assert OPENHANDS_THEME.secondary in help_text  # Secondary color (white)

        # Should not use generic color names
        assert "yellow" not in help_text.lower()
        assert "white" not in help_text.lower()

    def test_show_help_formatting(self):
        """Test that show_help has proper Rich markup formatting."""
        from openhands_cli.refactor.theme import OPENHANDS_THEME

        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        show_help(mock_main_display)

        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = help_widget.content

        # Check for proper Rich markup with theme colors
        assert f"[bold {OPENHANDS_THEME.primary}]" in help_text
        assert f"[/bold {OPENHANDS_THEME.primary}]" in help_text
        assert f"[{OPENHANDS_THEME.secondary}]" in help_text
        assert f"[/{OPENHANDS_THEME.secondary}]" in help_text
        assert "[dim]" in help_text

        # Should start and end with newlines for proper spacing
        assert help_text.startswith("\n")
        assert help_text.endswith("\n")
