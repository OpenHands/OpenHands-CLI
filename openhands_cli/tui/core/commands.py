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
from openhands_cli.tui.content.resources import LoadedResourcesInfo

if TYPE_CHECKING:
    from openhands_cli.tui.core.conversation_runner import ConversationRunner


# Available commands with descriptions after the command
COMMANDS = [
    DropdownItem(main="/help - Display available commands"),
    DropdownItem(main="/new - Start a new conversation"),
    DropdownItem(main="/history - Toggle conversation history"),
    DropdownItem(main="/confirm - Configure confirmation settings"),
    DropdownItem(main="/condense - Condense conversation history"),
    DropdownItem(main="/skills - View loaded skills, hooks, and MCPs"),
    DropdownItem(main="/agents - View available and active sub-agents"),
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
  [{secondary}]/skills[/{secondary}] - View loaded skills, hooks, and MCPs
  [{secondary}]/agents[/{secondary}] - View available and active sub-agents
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


def show_agents(
    scroll_view: VerticalScroll, runner: ConversationRunner | None = None
) -> None:
    """Display available agent types and active sub-agents.

    Args:
        scroll_view: The VerticalScroll widget to mount content to
        runner: The current conversation runner (for active sub-agent info)
    """
    # Access registry directly to avoid fragile string parsing
    from openhands.tools.delegate.registration import _agent_factories, _registry_lock

    primary = OPENHANDS_THEME.primary
    secondary = OPENHANDS_THEME.secondary

    lines = [f"\n[bold {primary}]Sub-Agents[/bold {primary}]"]

    # Section 1: Available agent types from the global registry
    lines.append(f"\n[bold {secondary}]Available Agent Types[/bold {secondary}]")

    # Always show default agent
    lines.append(f"  - [bold]default[/bold]: Default general-purpose agent")

    # Show user-registered agents
    with _registry_lock:
        user_factories = dict(_agent_factories)

    if user_factories:
        for name, factory in sorted(user_factories.items()):
            lines.append(f"  - [bold]{name}[/bold]: {factory.description}")

    # Section 2: Active sub-agents from the current conversation
    lines.append(f"\n[bold {secondary}]Active Sub-Agents[/bold {secondary}]")
    active_agents = _get_active_sub_agents(runner)
    if active_agents:
        for agent_id in active_agents:
            lines.append(f"  - {agent_id}")
    else:
        lines.append("  [dim]No active sub-agents in this session.[/dim]")

    agents_text = "\n".join(lines) + "\n"
    agents_widget = Static(agents_text, classes="agents-message")
    scroll_view.mount(agents_widget)


def _get_active_sub_agents(
    runner: ConversationRunner | None,
) -> list[str]:
    """Get active sub-agents from the conversation runner's delegate executor.

    Returns:
        List of agent IDs, or empty list if unavailable.
    """
    if runner is None or runner.conversation is None:
        return []

    try:
        agent = runner.conversation.agent
        delegate_tool = agent.tools_map.get("delegate")
        if delegate_tool is None or delegate_tool.executor is None:
            return []

        executor = delegate_tool.executor
        sub_agents = getattr(executor, "_sub_agents", {})
        if not sub_agents:
            return []

        return list(sub_agents.keys())
    except AttributeError as e:
        # Expected: conversation/agent/tools_map access on objects that don't have these attrs
        import logging

        logging.debug(f"Failed to get active sub-agents (expected if no conversation): {e}")
        return []
    except Exception as e:
        # Unexpected error - log it so we know something is wrong
        import logging

        logging.warning(f"Unexpected error getting active sub-agents: {e}", exc_info=True)
        return []
