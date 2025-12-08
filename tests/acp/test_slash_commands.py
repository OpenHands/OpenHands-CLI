"""Tests for ACP slash commands functionality."""

from openhands_cli.acp_impl.slash_commands import (
    create_help_text,
    get_available_slash_commands,
    parse_slash_command,
)


class TestParseSlashCommand:
    """Test the slash command parser."""

    def test_parse_simple_command(self):
        """Test parsing a simple slash command without arguments."""
        result = parse_slash_command("/help")
        assert result == ("help", "")

    def test_parse_command_with_argument(self):
        """Test parsing a slash command with an argument."""
        result = parse_slash_command("/confirm on")
        assert result == ("confirm", "on")

    def test_parse_command_with_multiple_arguments(self):
        """Test parsing a slash command with multiple space-separated arguments."""
        result = parse_slash_command("/confirm toggle extra")
        assert result == ("confirm", "toggle extra")

    def test_parse_command_with_extra_spaces(self):
        """Test parsing handles extra spaces correctly."""
        result = parse_slash_command("/confirm   on  ")
        assert result == ("confirm", "on")

    def test_parse_non_command(self):
        """Test that non-slash-command text returns None."""
        result = parse_slash_command("regular message")
        assert result is None

    def test_parse_empty_string(self):
        """Test that empty string returns None."""
        result = parse_slash_command("")
        assert result is None

    def test_parse_slash_only(self):
        """Test that a lone slash returns None."""
        result = parse_slash_command("/")
        assert result is None

    def test_parse_slash_with_spaces(self):
        """Test that slash followed by spaces returns None."""
        result = parse_slash_command("/   ")
        assert result is None


class TestSlashCommandFunctions:
    """Test the slash command helper functions."""

    def test_get_available_commands(self):
        """Test getting available slash commands."""
        commands = get_available_slash_commands()
        assert len(commands) == 2

        # Check that both commands are present
        command_names = {cmd.name for cmd in commands}
        assert command_names == {"/help", "/confirm"}

        # Check that descriptions exist
        help_cmd = next(cmd for cmd in commands if cmd.name == "/help")
        assert help_cmd.description
        confirm_cmd = next(cmd for cmd in commands if cmd.name == "/confirm")
        assert confirm_cmd.description

    def test_create_help_text(self):
        """Test creating help text."""
        help_text = create_help_text()
        assert help_text
        assert "Available slash commands" in help_text
        assert "/help" in help_text
        assert "/confirm" in help_text
