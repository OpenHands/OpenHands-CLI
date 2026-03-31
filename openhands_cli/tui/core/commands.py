"""Command definitions and handlers for OpenHands CLI.

This module contains all available commands, their descriptions,
and the logic for handling command execution.
"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Static
from textual_autocomplete import DropdownItem

from openhands_cli.shared.settings_commands import get_programmatic_setting_fields
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.resources import LoadedResourcesInfo


STATIC_COMMANDS = [
    ("help", "Display available commands"),
    ("new", "Start a new conversation"),
    ("history", "Toggle conversation history"),
    ("settings", "Open settings"),
    ("confirm", "Configure confirmation settings"),
    ("condense", "Condense conversation history"),
    ("skills", "View loaded skills, hooks, and MCPs"),
    ("feedback", "Send anonymous feedback about CLI"),
    ("exit", "Exit the application"),
]


def _build_commands() -> list[DropdownItem]:
    commands = [
        DropdownItem(main=f"/{command} - {description}")
        for command, description in STATIC_COMMANDS
    ]
    for field in get_programmatic_setting_fields():
        if field.slash_command is None:
            continue
        commands.append(
            DropdownItem(main=f"/{field.slash_command} - Update {field.label.lower()}")
        )
    return commands


COMMANDS = _build_commands()


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


def is_valid_command(user_input: str) -> bool:
    """Check if user input is an exact match for a valid command.

    Args:
        user_input: The user's input string

    Returns:
        True if input exactly matches a valid command, False otherwise
    """
    return user_input in get_valid_commands()


def show_help(scroll_view: VerticalScroll) -> None:
    """Display help information in the scrollable content area."""
    primary = OPENHANDS_THEME.primary
    secondary = OPENHANDS_THEME.secondary

    command_lines = []
    for command in COMMANDS:
        command_text = str(command.main)
        command_name, command_description = command_text.split(" - ", 1)
        command_lines.append(
            f"  [{secondary}]{command_name}[/{secondary}] - {command_description}"
        )
    help_text = (
        f"\n[bold {primary}]OpenHands CLI Help[/bold {primary}]\n"
        f"[dim]Available commands:[/dim]\n\n"
        + "\n".join(command_lines)
        + "\n\n[dim]Tips:[/dim]\n"
        "  • Type / and press Tab to see command suggestions\n"
        "  • Use arrow keys to navigate through suggestions\n"
        "  • Press Enter to select a command\n"
    )
    help_widget = Static(help_text, classes="help-message")
    scroll_view.mount(help_widget)


def show_skills(
    scroll_view: VerticalScroll, loaded_resources: LoadedResourcesInfo
) -> None:
    """Display loaded skills, hooks, and MCPs information in the scroll view.

    Args:
        scroll_view: The VerticalScroll widget to mount skills content to
        loaded_resources: Information about loaded resources
    """
    primary = OPENHANDS_THEME.primary

    # Build the skills text using the get_details method
    lines = [f"\n[bold {primary}]Loaded Resources[/bold {primary}]"]
    lines.append(f"[dim]Summary:[/dim] {loaded_resources.get_summary()}\n")
    details = loaded_resources.get_details()
    if details and details != "No resources loaded":
        lines.append(details)
    else:
        lines.append("[dim]No skills, hooks, or MCPs loaded.[/dim]")
    skills_text = "\n".join(lines)

    skills_widget = Static(skills_text, classes="skills-message")
    scroll_view.mount(skills_widget)
