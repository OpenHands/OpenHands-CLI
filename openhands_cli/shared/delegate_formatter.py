"""Centralized formatting for delegate tool titles.

This module provides a single source of truth for formatting delegate action
titles, used by both streaming (tool_state.py) and non-streaming (utils.py,
richlog_visualizer.py) code paths.
"""

from typing import Any

from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


def format_delegate_title(
    command: str | None,
    ids: list[str] | None = None,
    tasks: dict[str, Any] | None = None,
    agent_types: list[str] | None = None,
    include_agent_types: bool = False,
) -> str:
    """Format a title for delegate tool actions.

    Args:
        command: The delegate command ("spawn" or "delegate")
        ids: List of agent IDs for spawn command
        tasks: Dict of agent_id -> task for delegate command
        agent_types: Optional list of agent types (parallel to ids)
        include_agent_types: Whether to include agent types in spawn output

    Returns:
        Formatted title string
    """
    if command == "spawn":
        return _format_spawn_title(ids, agent_types, include_agent_types)
    elif command == "delegate":
        return _format_delegate_tasks_title(tasks)
    return "Delegate"


def _format_spawn_title(
    ids: list[str] | None,
    agent_types: list[str] | None,
    include_types: bool,
) -> str:
    """Format title for spawn command."""
    if not ids:
        return "Spawning sub-agents"

    if include_types and agent_types:
        agents_info = []
        for i, agent_id in enumerate(ids):
            agent_type = agent_types[i] if i < len(agent_types) else None
            if agent_type and agent_type != "default":
                agents_info.append(f"{agent_id} ({agent_type})")
            else:
                logger.warning("Length of IDs did not match agent types")
                agents_info.append(agent_id)
        agents_str = ", ".join(agents_info)
    else:
        agents_str = ", ".join(ids)

    return f"Spawning {len(ids)} sub-agent(s): {agents_str}"


def _format_delegate_tasks_title(tasks: dict[str, Any] | None) -> str:
    """Format title for delegate command."""
    if not tasks:
        return "Delegating tasks"
    return f"Delegating {len(tasks)} task(s) to: {', '.join(tasks.keys())}"
