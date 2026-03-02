"""Command definitions and handlers for OpenHands CLI.

This module contains all available commands, their descriptions,
and the logic for handling command execution.
"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Static
from textual_autocomplete import DropdownItem

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.resources import LoadedResourcesInfo


# Available commands with descriptions after the command
COMMANDS = [
    DropdownItem(main="/help - Display available commands"),
    DropdownItem(main="/new - Start a new conversation"),
    DropdownItem(main="/history - Toggle conversation history"),
    DropdownItem(main="/settings - Open settings"),
    DropdownItem(main="/confirm - Configure confirmation settings"),
    DropdownItem(main="/condense - Condense conversation history"),
    DropdownItem(main="/skills - View loaded skills, hooks, and MCPs"),
    DropdownItem(main="/plugin - Manage installed plugins"),
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
  [{secondary}]/settings[/{secondary}] - Open settings
  [{secondary}]/confirm[/{secondary}] - Configure confirmation settings
  [{secondary}]/condense[/{secondary}] - Condense conversation history
  [{secondary}]/skills[/{secondary}] - View loaded skills, hooks, and MCPs
  [{secondary}]/plugin[/{secondary}] - Manage installed plugins
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


def show_plugins(scroll_view: VerticalScroll) -> None:
    """Display installed plugins and plugin management help.

    Args:
        scroll_view: The VerticalScroll widget to mount plugins content to
    """
    from openhands.sdk.plugin import (
        get_installed_plugins_dir,
        list_installed_plugins,
    )

    primary = OPENHANDS_THEME.primary
    secondary = OPENHANDS_THEME.secondary

    lines = [f"\n[bold {primary}]Installed Plugins[/bold {primary}]"]

    # Get installed plugins
    try:
        installed_plugins = list_installed_plugins()
        plugins_dir = get_installed_plugins_dir()

        if installed_plugins:
            lines.append(f"[dim]Location:[/dim] {plugins_dir}\n")
            for plugin_info in installed_plugins:
                lines.append(
                    f"  [{secondary}]{plugin_info.name}[/{secondary}] "
                    f"v{plugin_info.version}"
                )
                if plugin_info.description:
                    lines.append(f"    [dim]{plugin_info.description}[/dim]")
                lines.append(f"    [dim]Source: {plugin_info.source}[/dim]")
                if plugin_info.resolved_ref:
                    lines.append(f"    [dim]Ref: {plugin_info.resolved_ref[:8]}[/dim]")
                lines.append("")
        else:
            lines.append("[dim]No plugins installed.[/dim]\n")

    except Exception as e:
        lines.append(f"[red]Error loading plugins: {e}[/red]\n")

    # Add usage instructions
    lines.append(f"[bold {primary}]Plugin Management[/bold {primary}]")
    lines.append("[dim]Use the following commands in your terminal:[/dim]\n")
    lines.append(
        f"  [{secondary}]Install:[/{secondary}] "
        "openhands plugin install github:owner/repo"
    )
    lines.append(
        f"  [{secondary}]Uninstall:[/{secondary}] "
        "openhands plugin uninstall plugin-name"
    )
    lines.append(
        f"  [{secondary}]List:[/{secondary}] "
        "openhands plugin list"
    )
    lines.append(
        f"  [{secondary}]Update:[/{secondary}] "
        "openhands plugin update plugin-name"
    )
    lines.append("")
    lines.append("[dim]Supported sources:[/dim]")
    lines.append("  • github:owner/repo - GitHub repository")
    lines.append("  • https://github.com/owner/repo - Git URL")
    lines.append("  • /local/path - Local directory")

    plugins_text = "\n".join(lines)
    plugins_widget = Static(plugins_text, classes="plugins-message")
    scroll_view.mount(plugins_widget)
