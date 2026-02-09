"""Loaded resources information for OpenHands CLI.

This module contains dataclasses for tracking loaded skills, hooks, tools,
and MCPs that are activated in a conversation, as well as utility functions
for collecting this information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openhands.sdk import Agent


@dataclass
class SkillInfo:
    """Information about a loaded skill."""

    name: str
    description: str | None = None
    source: str | None = None


@dataclass
class HookInfo:
    """Information about loaded hooks."""

    hook_type: str
    count: int


@dataclass
class ToolInfo:
    """Information about a loaded tool."""

    name: str


@dataclass
class MCPInfo:
    """Information about a loaded MCP server."""

    name: str
    transport: str | None = None
    enabled: bool = True


@dataclass
class LoadedResourcesInfo:
    """Information about loaded skills, hooks, tools, and MCPs for a conversation."""

    skills: list[SkillInfo] = field(default_factory=list)
    hooks: list[HookInfo] = field(default_factory=list)
    tools: list[ToolInfo] = field(default_factory=list)
    mcps: list[MCPInfo] = field(default_factory=list)

    @property
    def skills_count(self) -> int:
        return len(self.skills)

    @property
    def hooks_count(self) -> int:
        return sum(h.count for h in self.hooks)

    @property
    def tools_count(self) -> int:
        return len(self.tools)

    @property
    def mcps_count(self) -> int:
        return len(self.mcps)

    def has_resources(self) -> bool:
        """Check if any resources are loaded."""
        return bool(self.skills or self.hooks or self.tools or self.mcps)

    def get_summary(self) -> str:
        """Get a summary string of loaded resources."""
        parts = []
        if self.skills_count > 0:
            parts.append(
                f"{self.skills_count} skill{'s' if self.skills_count != 1 else ''}"
            )
        if self.hooks_count > 0:
            parts.append(
                f"{self.hooks_count} hook{'s' if self.hooks_count != 1 else ''}"
            )
        if self.tools_count > 0:
            parts.append(
                f"{self.tools_count} tool{'s' if self.tools_count != 1 else ''}"
            )
        if self.mcps_count > 0:
            parts.append(f"{self.mcps_count} MCP{'s' if self.mcps_count != 1 else ''}")
        return ", ".join(parts) if parts else "No resources loaded"

    def get_details(self) -> str:
        """Get detailed information about loaded resources as plain text."""
        lines = []

        if self.skills:
            lines.append(f"Skills ({self.skills_count}):")
            for skill in self.skills:
                lines.append(f"  • {skill.name}")
                if skill.description:
                    lines.append(f"      {skill.description}")
                if skill.source:
                    lines.append(f"      ({skill.source})")

        if self.hooks:
            if lines:
                lines.append("")
            lines.append(f"Hooks ({self.hooks_count}):")
            for hook in self.hooks:
                lines.append(f"  • {hook.hook_type}: {hook.count}")

        if self.tools:
            if lines:
                lines.append("")
            lines.append(f"Tools ({self.tools_count}):")
            for tool in self.tools:
                lines.append(f"  • {tool.name}")

        if self.mcps:
            if lines:
                lines.append("")
            lines.append(f"MCPs ({self.mcps_count}):")
            for mcp in self.mcps:
                lines.append(f"  • {mcp.name}")
                if mcp.transport:
                    lines.append(f"      ({mcp.transport})")

        return "\n".join(lines) if lines else "No resources loaded"


def _collect_skills(agent: Agent) -> list[SkillInfo]:
    """Collect skills information from an agent."""
    skills = []
    if agent.agent_context and agent.agent_context.skills:
        for skill in agent.agent_context.skills:
            skills.append(
                SkillInfo(
                    name=skill.name,
                    description=skill.description,
                    source=skill.source,
                )
            )
    return skills


def _collect_tools(agent: Agent) -> list[ToolInfo]:
    """Collect tools information from an agent."""
    tools = []
    if agent.tools:
        for tool in agent.tools:
            tools.append(ToolInfo(name=tool.name))
    return tools


def _collect_hooks(working_dir: Path | str | None) -> list[HookInfo]:
    """Collect hooks information from the hook configuration.

    Args:
        working_dir: The working directory to load hooks from

    Returns:
        List of HookInfo objects
    """
    hooks = []
    try:
        from openhands.sdk.hooks import HookConfig

        hook_config = HookConfig.load(working_dir=working_dir)
        hook_types = [
            ("pre_tool_use", hook_config.pre_tool_use),
            ("post_tool_use", hook_config.post_tool_use),
            ("user_prompt_submit", hook_config.user_prompt_submit),
            ("session_start", hook_config.session_start),
            ("session_end", hook_config.session_end),
            ("stop", hook_config.stop),
        ]
        for hook_type, hook_list in hook_types:
            if hook_list:
                hooks.append(HookInfo(hook_type=hook_type, count=len(hook_list)))
    except Exception:
        pass

    return hooks


def _collect_mcps() -> list[MCPInfo]:
    """Collect MCP server information."""
    mcps = []
    try:
        from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer

        from openhands_cli.mcp.mcp_utils import list_enabled_servers

        enabled_servers = list_enabled_servers()
        for name, server in enabled_servers.items():
            if isinstance(server, StdioMCPServer):
                transport = "stdio"
            elif isinstance(server, RemoteMCPServer):
                transport = server.transport
            else:
                transport = None
            mcps.append(MCPInfo(name=name, transport=transport, enabled=True))
    except Exception:
        pass

    return mcps


def collect_loaded_resources(
    agent: Agent | None = None,
    working_dir: Path | str | None = None,
) -> LoadedResourcesInfo:
    """Collect information about loaded resources for a conversation.

    This function gathers information about skills, hooks, tools, and MCPs
    that are activated for the current conversation.

    Args:
        agent: The agent to collect resources from (for skills and tools)
        working_dir: The working directory to load hooks from

    Returns:
        LoadedResourcesInfo containing all collected resource information
    """
    resources = LoadedResourcesInfo()

    # Collect from agent if provided
    if agent:
        resources.skills = _collect_skills(agent)
        resources.tools = _collect_tools(agent)

    # Collect hooks
    resources.hooks = _collect_hooks(working_dir)

    # Collect MCPs
    resources.mcps = _collect_mcps()

    return resources
