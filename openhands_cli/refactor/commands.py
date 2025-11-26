"""Command definitions and handlers for OpenHands CLI.

This module contains all available commands, their descriptions,
and the logic for handling command execution.
"""

from textual.widgets import RichLog
from textual_autocomplete import DropdownItem


# Available commands with descriptions after the command
COMMANDS = [
    DropdownItem(main="/help - Display available commands"),
    DropdownItem(main="/exit - Exit the application"),
]


def show_help(main_display: RichLog) -> None:
    """Display help information in the main display.

    Args:
        main_display: The RichLog widget to write help content to
    """
    help_text = """
[bold $primary]OpenHands CLI Help[/bold $primary]
[dim]Available commands:[/dim]

  [$secondary]/help[/$secondary] - Display available commands
  [$secondary]/exit[/$secondary] - Exit the application

[dim]Tips:[/dim]
  • Type / and press Tab to see command suggestions
  • Use arrow keys to navigate through suggestions
  • Press Enter to select a command
"""
    main_display.write(help_text)
