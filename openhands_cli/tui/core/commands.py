"""Command definitions and handlers for OpenHands CLI.

This module contains all available commands, their descriptions,
and the logic for handling command execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import VerticalScroll
from textual.widgets import Static
from textual_autocomplete import DropdownItem

from openhands_cli.theme import OPENHANDS_THEME


if TYPE_CHECKING:
    from openhands_cli.tui.content.resources import LoadedResourcesInfo


# Available commands with descriptions after the command
COMMANDS = [
    DropdownItem(main="/help - Display available commands"),
    DropdownItem(main="/new - Start a new conversation"),
    DropdownItem(main="/history - Toggle conversation history"),
    DropdownItem(main="/confirm - Configure confirmation settings"),
    DropdownItem(main="/condense - Condense conversation history"),
    DropdownItem(main="/skills - View loaded skills, hooks, and tools"),
    DropdownItem(main="/feedback - Send anonymous feedback about CLI"),
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


def is_valid_command(user_input: str) -> bool:
    """Check if user input is an exact match for a valid command.

    Args:
        user_input: The user's input string

    Returns:
        True if input exactly matches a valid command, False otherwise
    """
    return user_input in get_valid_commands()


def show_help(scroll_view: VerticalScroll) -> None:
    """Display help information in the scrollable content area.

    Args:
        scroll_view: The VerticalScroll widget to mount help content to
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
  [{secondary}]/skills[/{secondary}] - View loaded skills, hooks, and tools
  [{secondary}]/feedback[/{secondary}] - Send anonymous feedback about CLI
  [{secondary}]/exit[/{secondary}] - Exit the application

[dim]Tips:[/dim]
  • Type / and press Tab to see command suggestions
  • Use arrow keys to navigate through suggestions
  • Press Enter to select a command
"""
    help_widget = Static(help_text, classes="help-message")
    scroll_view.mount(help_widget)


def show_skills(
    scroll_view: VerticalScroll, loaded_resources: LoadedResourcesInfo | None
) -> None:
    """Display loaded skills, hooks, tools, and MCPs information in the scroll view.

    Args:
        scroll_view: The VerticalScroll widget to mount skills content to
        loaded_resources: Information about loaded resources, or None if not available
    """
    primary = OPENHANDS_THEME.primary
    secondary = OPENHANDS_THEME.secondary

    if loaded_resources is None:
        skills_text = f"""
[bold {primary}]Loaded Resources[/bold {primary}]
[dim]No resources information available.[/dim]
"""
    else:
        # Build the skills text
        lines = [f"\n[bold {primary}]Loaded Resources[/bold {primary}]"]
        lines.append(f"[dim]Summary: {loaded_resources.get_summary()}[/dim]\n")

        if loaded_resources.skills:
            lines.append(
                f"[{primary}]Skills ({loaded_resources.skills_count}):[/{primary}]"
            )
            for skill in loaded_resources.skills:
                desc = f" - {skill.description}" if skill.description else ""
                source = (
                    f" [{secondary}]({skill.source})[/{secondary}]"
                    if skill.source
                    else ""
                )
                lines.append(f"  • {skill.name}{desc}{source}")
            lines.append("")

        if loaded_resources.hooks:
            lines.append(
                f"[{primary}]Hooks ({loaded_resources.hooks_count}):[/{primary}]"
            )
            for hook in loaded_resources.hooks:
                lines.append(f"  • {hook.hook_type}: {hook.count}")
            lines.append("")

        if loaded_resources.tools:
            lines.append(
                f"[{primary}]Tools ({loaded_resources.tools_count}):[/{primary}]"
            )
            for tool in loaded_resources.tools:
                desc = f" - {tool.description}" if tool.description else ""
                lines.append(f"  • {tool.name}{desc}")
            lines.append("")

        if loaded_resources.mcps:
            lines.append(
                f"[{primary}]MCPs ({loaded_resources.mcps_count}):[/{primary}]"
            )
            for mcp in loaded_resources.mcps:
                transport = (
                    f" [{secondary}]({mcp.transport})[/{secondary}]"
                    if mcp.transport
                    else ""
                )
                lines.append(f"  • {mcp.name}{transport}")
            lines.append("")

        if not (
            loaded_resources.skills
            or loaded_resources.hooks
            or loaded_resources.tools
            or loaded_resources.mcps
        ):
            lines.append("[dim]No skills, hooks, tools, or MCPs loaded.[/dim]")

        skills_text = "\n".join(lines)

    skills_widget = Static(skills_text, classes="skills-message")
    scroll_view.mount(skills_widget)
