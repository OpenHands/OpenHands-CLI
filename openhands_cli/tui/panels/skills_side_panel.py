"""Skills side panel widget for displaying skills information."""

from textual.app import App
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static

from openhands.sdk import Agent
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.panels.skills_panel_style import SKILLS_PANEL_STYLE


class SkillsSidePanel(VerticalScroll):
    """Side panel widget that displays skills information."""

    DEFAULT_CSS = SKILLS_PANEL_STYLE

    def __init__(self, app: App, agent: Agent | None = None, **kwargs):
        """Initialize the skills side panel.

        Args:
            app: The Textual app instance (used for mounting/unmounting)
            agent: The OpenHands agent instance to get skills from
        """
        super().__init__(**kwargs)
        self._oh_app = app
        self.agent = agent

    def toggle(self) -> None:
        """Toggle the skills side panel on/off."""
        if self.is_on_screen:
            self.remove()
            return

        content_area = self._oh_app.query_one("#content_area", Horizontal)
        content_area.mount(self)

    def compose(self):
        """Compose the skills side panel content."""
        yield Static("Skills", classes="skills-header")
        yield Static("", id="skills-content")

    def on_mount(self):
        """Called when the panel is mounted."""
        self.refresh_content()

    def refresh_content(self):
        """Refresh the skills content."""
        content_widget = self.query_one("#skills-content", Static)
        # Check if agent failed to load
        if not self.agent:
            content_parts = [
                f"[{OPENHANDS_THEME.error}]Failed to load skills."
                f"[/{OPENHANDS_THEME.error}]",
                f"[{OPENHANDS_THEME.error}]Settings file is corrupted!"
                f"[/{OPENHANDS_THEME.error}]",
            ]
            content_widget.update("\n".join(content_parts))
            return

        # Get skills from agent context
        if not self.agent.agent_context:
            content_parts = [
                f"[{OPENHANDS_THEME.warning}]No agent context found"
                f"[/{OPENHANDS_THEME.warning}]",
            ]
            content_widget.update("\n".join(content_parts))
            return

        skills = self.agent.agent_context.skills
        content_parts = []
        if not skills:
            content_parts.append(
                f"[{OPENHANDS_THEME.warning}]No skills loaded"
                f"[/{OPENHANDS_THEME.warning}]"
            )
            content_widget.update("\n".join(content_parts))
            return

        content_parts.append(f"[bold]Total Skills: {len(skills)}[/bold]")
        content_parts.append("")
        always_active = []
        keyword_triggered = []
        task_triggered = []

        for skill in skills:
            if not skill.trigger:
                always_active.append(skill)
            elif hasattr(skill.trigger, "keywords"):
                keyword_triggered.append(skill)
            elif hasattr(skill.trigger, "triggers"):
                task_triggered.append(skill)

        # Show always-active skills
        if always_active:
            content_parts.append(
                f"[{OPENHANDS_THEME.success}]Always Active ({len(always_active)}):[/]"
            )
            for skill in always_active:
                content_parts.append(f"  [{OPENHANDS_THEME.primary}]• {skill.name}[/]")
                if skill.source:
                    content_parts.append(f"    Source: {skill.source}")
            content_parts.append("")

        # Show keyword-triggered skills
        if keyword_triggered:
            content_parts.append(
                f"[{OPENHANDS_THEME.accent}]Keyword-Triggered "
                f"({len(keyword_triggered)}):[/]"
            )
            for skill in keyword_triggered:
                content_parts.append(f"  [{OPENHANDS_THEME.primary}]• {skill.name}[/]")
                if hasattr(skill.trigger, "keywords") and skill.trigger.keywords:
                    keywords_str = ", ".join(skill.trigger.keywords)
                    content_parts.append(
                        f"    [{OPENHANDS_THEME.accent}]Keywords: {keywords_str}[/]"
                    )
                if skill.source:
                    content_parts.append(f"    Source: {skill.source}")
            content_parts.append("")

        # Show task-triggered skills
        if task_triggered:
            content_parts.append(
                f"[{OPENHANDS_THEME.accent}]Task-Triggered ({len(task_triggered)}):[/]"
            )
            for skill in task_triggered:
                content_parts.append(f"  [{OPENHANDS_THEME.primary}]• {skill.name}[/]")
                if skill.source:
                    content_parts.append(f"    Source: {skill.source}")
            content_parts.append("")

        # Join all content and update the widget
        content_text = "\n".join(content_parts)
        content_widget.update(content_text)
