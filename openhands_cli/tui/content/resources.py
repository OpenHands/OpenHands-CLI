"""Loaded resources information for OpenHands CLI.

This module contains dataclasses for tracking loaded skills, hooks, and tools
that are activated in a conversation.
"""

from dataclasses import dataclass, field

from textual.theme import Theme


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
    description: str | None = None


@dataclass
class LoadedResourcesInfo:
    """Information about loaded skills, hooks, and tools for a conversation."""

    skills: list[SkillInfo] = field(default_factory=list)
    hooks: list[HookInfo] = field(default_factory=list)
    tools: list[ToolInfo] = field(default_factory=list)

    @property
    def skills_count(self) -> int:
        return len(self.skills)

    @property
    def hooks_count(self) -> int:
        return sum(h.count for h in self.hooks)

    @property
    def tools_count(self) -> int:
        return len(self.tools)

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
        return ", ".join(parts) if parts else "No resources loaded"

    def get_details(self, *, theme: Theme) -> str:
        """Get detailed information about loaded resources with Rich markup."""
        lines = []
        primary = theme.primary
        secondary = theme.secondary

        if self.skills:
            lines.append(f"[{primary}]Skills ({self.skills_count}):[/{primary}]")
            for skill in self.skills:
                desc = f" - {skill.description}" if skill.description else ""
                source = (
                    f" [{secondary}]({skill.source})[/{secondary}]"
                    if skill.source
                    else ""
                )
                lines.append(f"  • {skill.name}{desc}{source}")

        if self.hooks:
            lines.append(f"\n[{primary}]Hooks ({self.hooks_count}):[/{primary}]")
            for hook in self.hooks:
                lines.append(f"  • {hook.hook_type}: {hook.count}")

        if self.tools:
            lines.append(f"\n[{primary}]Tools ({self.tools_count}):[/{primary}]")
            for tool in self.tools:
                desc = f" - {tool.description}" if tool.description else ""
                lines.append(f"  • {tool.name}{desc}")

        return "\n".join(lines) if lines else "No resources loaded"
