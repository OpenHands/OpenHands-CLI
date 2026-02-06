"""Command definitions and handlers for OpenHands CLI.

This module contains all available commands, their descriptions,
and the logic for handling command execution.
"""

from textual.containers import VerticalScroll
from textual.widgets import Static
from textual_autocomplete import DropdownItem

from openhands_cli.theme import OPENHANDS_THEME


# Available commands with descriptions after the command
COMMANDS = [
    DropdownItem(main="/help - Display available commands"),
    DropdownItem(main="/new - Start a new conversation"),
    DropdownItem(main="/history - Toggle conversation history"),
    DropdownItem(main="/confirm - Configure confirmation settings"),
    DropdownItem(main="/condense - Condense conversation history"),
    DropdownItem(main="/feedback - Send anonymous feedback about CLI"),
    DropdownItem(main="/export - Save the current conversation to Markdown/JSON"),
    DropdownItem(main="/exit - Exit the application"),
]


def get_valid_commands() -> set[str]:
    """Extract valid command names from COMMANDS list.

    Returns:
        Set of valid command strings (e.g., {"/help", "/exit"})
    """
    valid_commands = set()
    for command_item in COMMANDS:
        command_text = str(command_item.main)
        # Extract command part (before " - " if present)
        if " - " in command_text:
            command = command_text.split(" - ")[0]
        else:
            command = command_text
        valid_commands.add(command)
    return valid_commands


def extract_command_and_args(user_input: str) -> tuple[str | None, str]:
    """Parse user input into a command and optional arguments."""

    stripped = user_input.strip()
    if not stripped.startswith("/") or len(stripped) == 1:
        return None, ""

    parts = stripped.split(maxsplit=1)
    command = parts[0]
    args = parts[1].strip() if len(parts) > 1 else ""

    if command not in get_valid_commands():
        return None, ""

    return command, args


def is_valid_command(user_input: str) -> bool:
    """Return True if user_input starts with a known slash command."""

    command, _ = extract_command_and_args(user_input)
    return command is not None


def show_help(main_display: VerticalScroll) -> None:
    """Display help information in the main display.

    Args:
        main_display: The VerticalScroll widget to mount help content to
    """
    primary = OPENHANDS_THEME.primary
    secondary = OPENHANDS_THEME.secondary

    help_text = f"""
[bold {primary}]OpenHands CLI Help[/bold {primary}]
[dim]Available commands:[/dim]

  [{secondary}]/help[/{secondary}] - Display available commands
  [{secondary}]/new[/{secondary}] - Start a new conversation
  [{secondary}]/history[/{secondary}] - Toggle conversation history
  [{secondary}]/confirm[/{secondary}] - Configure confirmation settings
  [{secondary}]/condense[/{secondary}] - Condense conversation history
  [{secondary}]/feedback[/{secondary}] - Send anonymous feedback about CLI
  [{secondary}]/export[/{secondary}] - Save current conversation as Markdown/JSON
  [{secondary}]/exit[/{secondary}] - Exit the application

[dim]Tips:[/dim]
  • Type / and press Tab to see command suggestions
  • Use arrow keys to navigate through suggestions
  • Press Enter to select a command
"""
    help_widget = Static(help_text, classes="help-message")
    main_display.mount(help_widget)
