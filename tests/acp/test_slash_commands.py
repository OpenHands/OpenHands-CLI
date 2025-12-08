"""Tests for ACP slash commands functionality."""

import pytest

from openhands_cli.acp_impl.slash_commands import (
    SlashCommandRegistry,
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


class TestSlashCommandRegistry:
    """Test the slash command registry."""

    async def test_register_and_execute_command(self):
        """Test registering and executing a command."""
        registry = SlashCommandRegistry()
        called_with = []

        async def test_handler(session_id: str, argument: str) -> str:
            called_with.append((session_id, argument))
            return f"Handled: {argument}"

        registry.register("test", "Test command", test_handler)

        result = await registry.execute("test", "session123", "arg1")
        assert result == "Handled: arg1"
        assert called_with == [("session123", "arg1")]

    async def test_execute_nonexistent_command(self):
        """Test executing a command that doesn't exist."""
        registry = SlashCommandRegistry()

        result = await registry.execute("nonexistent", "session123", "")
        assert "Unknown command" in result
        assert "nonexistent" in result

    def test_get_available_commands(self):
        """Test retrieving available commands."""
        registry = SlashCommandRegistry()

        async def dummy_handler(session_id: str, argument: str) -> str:
            return "dummy"

        registry.register("cmd1", "Command 1", dummy_handler)
        registry.register("cmd2", "Command 2", dummy_handler)

        commands = registry.get_available_commands()
        assert len(commands) == 2

        # Check that both commands are present
        command_names = {cmd.name for cmd in commands}
        assert command_names == {"/cmd1", "/cmd2"}

        # Check that descriptions are correct
        cmd1 = next(cmd for cmd in commands if cmd.name == "/cmd1")
        assert cmd1.description == "Command 1"

    def test_register_duplicate_command(self):
        """Test that registering a duplicate command replaces the old one."""
        registry = SlashCommandRegistry()

        async def handler1(session_id: str, argument: str) -> str:
            return "handler1"

        async def handler2(session_id: str, argument: str) -> str:
            return "handler2"

        registry.register("test", "First", handler1)
        registry.register("test", "Second", handler2)

        # Should have only one command
        commands = registry.get_available_commands()
        assert len(commands) == 1
        assert commands[0].description == "Second"


class TestSlashCommandIntegration:
    """Integration tests for slash commands with confirmation mode."""

    async def test_confirm_command_on(self):
        """Test /confirm on command."""
        registry = SlashCommandRegistry()
        confirmation_states = {}

        async def confirm_handler(session_id: str, argument: str) -> str:
            arg = argument.strip().lower()
            if arg == "on":
                confirmation_states[session_id] = True
                return "Confirmation mode enabled."
            elif arg == "off":
                confirmation_states[session_id] = False
                return "Confirmation mode disabled."
            elif arg == "toggle":
                confirmation_states[session_id] = not confirmation_states.get(
                    session_id, False
                )
                state = "enabled" if confirmation_states[session_id] else "disabled"
                return f"Confirmation mode {state}."
            else:
                return "Usage: /confirm [on|off|toggle]"

        registry.register(
            "confirm",
            "Control confirmation mode",
            confirm_handler,
        )

        # Test turning on
        result = await registry.execute("confirm", "session1", "on")
        assert result is not None
        assert "enabled" in result.lower()
        assert confirmation_states.get("session1") is True

        # Test turning off
        result = await registry.execute("confirm", "session1", "off")
        assert result is not None
        assert "disabled" in result.lower()
        assert confirmation_states.get("session1") is False

        # Test toggle
        result = await registry.execute("confirm", "session1", "toggle")
        assert result is not None
        assert "enabled" in result.lower()
        assert confirmation_states.get("session1") is True

    async def test_help_command(self):
        """Test /help command."""
        registry = SlashCommandRegistry()

        async def help_handler(session_id: str, argument: str) -> str:
            commands = registry.get_available_commands()
            if not commands:
                return "No commands available."

            help_text = "Available commands:\n"
            for cmd in commands:
                help_text += f"\n{cmd.name}: {cmd.description}"
            return help_text

        registry.register("help", "Show available commands", help_handler)

        result = await registry.execute("help", "session1", "")
        assert "Available commands" in result
        assert "/help" in result
