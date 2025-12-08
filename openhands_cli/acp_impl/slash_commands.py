"""Slash commands implementation for ACP."""

import logging
from typing import Callable

from acp.schema import AvailableCommand


logger = logging.getLogger(__name__)


class SlashCommandRegistry:
    """Registry for slash commands."""

    def __init__(self):
        """Initialize the slash command registry."""
        self._commands: dict[str, Callable] = {}
        self._descriptions: dict[str, str] = {}

    def register(self, name: str, description: str, handler: Callable) -> None:
        """Register a slash command.

        Args:
            name: Command name (without leading slash)
            description: Human-readable description
            handler: Function to handle the command
        """
        self._commands[name] = handler
        self._descriptions[name] = description
        logger.debug(f"Registered slash command: /{name}")

    def get_available_commands(self) -> list[AvailableCommand]:
        """Get list of available commands in ACP format.

        Returns:
            List of AvailableCommand objects
        """
        return [
            AvailableCommand(
                name=f"/{name}",
                description=self._descriptions[name],
            )
            for name in sorted(self._commands.keys())
        ]

    async def execute(self, command: str, *args, **kwargs) -> str | None:
        """Execute a slash command.

        Args:
            command: Command name (without leading slash)
            *args: Positional arguments for the handler
            **kwargs: Keyword arguments for the handler

        Returns:
            Response message or None
        """
        if command not in self._commands:
            available = ", ".join(f"/{cmd}" for cmd in sorted(self._commands.keys()))
            return (
                f"Unknown command: /{command}\n\n"
                f"Available commands: {available}\n"
                f"Use /help for more information."
            )

        try:
            handler = self._commands[command]
            result = handler(*args, **kwargs)
            # Support both sync and async handlers
            if hasattr(result, "__await__"):
                result = await result
            return result
        except Exception as e:
            logger.error(f"Error executing command /{command}: {e}", exc_info=True)
            return f"Error executing command /{command}: {str(e)}"


def parse_slash_command(text: str) -> tuple[str, str] | None:
    """Parse a slash command from user input.

    Args:
        text: User input text

    Returns:
        Tuple of (command, argument) if text is a slash command, None otherwise
    """
    text = text.strip()
    if not text.startswith("/"):
        return None

    # Remove leading slash
    text = text[1:].strip()

    # If nothing after the slash, it's not a valid command
    if not text:
        return None

    # Split into command and argument
    parts = text.split(None, 1)
    command = parts[0].lower()
    argument = parts[1] if len(parts) > 1 else ""

    return command, argument
