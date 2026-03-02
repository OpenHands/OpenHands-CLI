"""Slash command parsing utilities.

This module provides common slash command parsing functionality
that can be used by both ACP and TUI implementations.
"""


def parse_slash_command(text: str) -> tuple[str, str] | None:
    """Parse a slash command from user input.

    Args:
        text: User input text

    Returns:
        Tuple of (command, argument) if text is a slash command, None otherwise.
        The command is always lowercase.

    Examples:
        >>> parse_slash_command("/help")
        ('help', '')
        >>> parse_slash_command("/confirm always-ask")
        ('confirm', 'always-ask')
        >>> parse_slash_command("not a command")
        None
        >>> parse_slash_command("/")
        None
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
