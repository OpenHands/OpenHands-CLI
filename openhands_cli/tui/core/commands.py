"""Command definitions and handlers for OpenHands CLI.

This module contains all available commands, their descriptions,
and the logic for handling command execution.
"""

from collections.abc import Callable

from textual.containers import VerticalScroll
from textual.widgets import Static
from textual_autocomplete import DropdownItem

from openhands_cli.theme import OPENHANDS_THEME


# ---------------------------------------------------------------------------
# Condition functions for conditional commands
# ---------------------------------------------------------------------------
def _show_in_local_mode(is_cloud_mode: bool) -> bool:
    """Command available only in local mode (not logged into cloud)."""
    return not is_cloud_mode


# For future use:
# def _show_in_cloud_mode(is_cloud_mode: bool) -> bool:
#     """Command available only in cloud mode."""
#     return is_cloud_mode


# ---------------------------------------------------------------------------
# Command definitions
# ---------------------------------------------------------------------------

# Base commands always available
COMMANDS = [
    DropdownItem(main="/help - Display available commands"),
    DropdownItem(main="/new - Start a new conversation"),
    DropdownItem(main="/confirm - Configure confirmation settings"),
    DropdownItem(main="/condense - Condense conversation history"),
    DropdownItem(main="/feedback - Send anonymous feedback about CLI"),
    DropdownItem(main="/exit - Exit the application"),
]

# Conditional commands: (command, condition_func)
# condition_func takes is_cloud_mode and returns True if command should be shown
_CONDITIONAL_COMMANDS: list[tuple[DropdownItem, Callable[[bool], bool]]] = [
    (DropdownItem(main="/history - Toggle conversation history"), _show_in_local_mode),
]


def get_commands(*, is_cloud_mode: bool = False) -> list[DropdownItem]:
    """Get available commands, including conditional ones based on mode.

    Args:
        is_cloud_mode: If True, exclude local-only commands like /history.

    Returns:
        List of DropdownItem commands available in the current mode.
    """
    result = list(COMMANDS)

    # Add conditional commands if their condition is satisfied
    for cmd, should_show in _CONDITIONAL_COMMANDS:
        if should_show(is_cloud_mode):
            # Insert after /new (index 1) to keep logical order
            result.insert(2, cmd)

    return result


def get_valid_commands(*, is_cloud_mode: bool = False) -> set[str]:
    """Extract valid command names from commands list.

    Args:
        is_cloud_mode: If True, exclude local-only commands.

    Returns:
        Set of valid command strings (e.g., {"/help", "/exit"})
    """
    valid_commands = set()
    for command_item in get_commands(is_cloud_mode=is_cloud_mode):
        command_text = str(command_item.main)
        # Extract command part (before " - " if present)
        if " - " in command_text:
            command = command_text.split(" - ")[0]
        else:
            command = command_text
        valid_commands.add(command)
    return valid_commands


def is_valid_command(user_input: str, *, is_cloud_mode: bool = False) -> bool:
    """Check if user input is an exact match for a valid command.

    Args:
        user_input: The user's input string
        is_cloud_mode: If True, exclude local-only commands.

    Returns:
        True if input exactly matches a valid command, False otherwise
    """
    return user_input in get_valid_commands(is_cloud_mode=is_cloud_mode)


def show_help(main_display: VerticalScroll, *, is_cloud_mode: bool = False) -> None:
    """Display help information in the main display.

    Args:
        main_display: The VerticalScroll widget to mount help content to
        is_cloud_mode: If True, exclude local-only commands from help.
    """
    primary = OPENHANDS_THEME.primary
    secondary = OPENHANDS_THEME.secondary

    # Base commands (always available)
    base_help = f"""
[bold {primary}]OpenHands CLI Help[/bold {primary}]
[dim]Available commands:[/dim]

  [{secondary}]/help[/{secondary}] - Display available commands
  [{secondary}]/new[/{secondary}] - Start a new conversation
"""

    # Add /history line only in local mode
    history_line = ""
    if not is_cloud_mode:
        history_line = (
            f"  [{secondary}]/history[/{secondary}] - "
            f"Toggle conversation history (Ctrl+H)\n"
        )

    rest_help = f"""\
  [{secondary}]/confirm[/{secondary}] - Configure confirmation settings
  [{secondary}]/condense[/{secondary}] - Condense conversation history
  [{secondary}]/feedback[/{secondary}] - Send anonymous feedback about CLI
  [{secondary}]/exit[/{secondary}] - Exit the application

[dim]Tips:[/dim]
  • Type / and press Tab to see command suggestions
  • Use arrow keys to navigate through suggestions
  • Press Enter to select a command
"""

    help_text = base_help + history_line + rest_help
    help_widget = Static(help_text, classes="help-message")
    main_display.mount(help_widget)
