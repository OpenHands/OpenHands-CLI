"""Plan side panel widget for displaying agent task plan."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError
from textual.app import App
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Static

from openhands.tools.task_tracker.definition import (
    TaskItem,
    TaskTrackerStatusType,
)
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.panels.plan_panel_style import PLAN_PANEL_STYLE


# Status icons for visual representation
STATUS_ICONS: dict[TaskTrackerStatusType, str] = {
    "todo": "⏳",
    "in_progress": "🔄",
    "done": "✅",
}


class PlanSidePanel(VerticalScroll):
    """Side panel widget that displays the agent's task plan.

    This panel is self-sufficient - it knows its persistence directory and can
    reload tasks from disk when needed. External callers just need to call
    refresh_from_disk() to trigger an update.
    """

    DEFAULT_CSS = PLAN_PANEL_STYLE

    def __init__(self, **kwargs):
        """Initialize the Plan side panel."""
        super().__init__(**kwargs)
        self._task_list: list[TaskItem] = []
        self._persistence_dir: str | Path | None = None

    @property
    def task_list(self) -> list[TaskItem]:
        """Get the current task list."""
        return self._task_list

    @property
    def persistence_dir(self) -> str | Path | None:
        """Get the persistence directory path."""
        return self._persistence_dir

    def set_persistence_dir(self, path: str | Path | None) -> None:
        """Set the persistence directory and load initial tasks.

        Args:
            path: Path to the conversation's persistence directory
        """
        self._persistence_dir = path
        self.refresh_from_disk()

    def refresh_from_disk(self) -> None:
        """Reload tasks from the persistence directory and update display.

        This method reads the TASKS.json file from the persistence directory
        and updates the panel's content. It's safe to call even if no
        persistence directory is set or if the file doesn't exist.
        """
        self._task_list = self._load_tasks_from_path(self._persistence_dir) or []
        self._refresh_content()

    @classmethod
    def get_or_create(cls, app: App) -> PlanSidePanel:
        """Get existing panel or create a new one.

        Args:
            app: The Textual app instance

        Returns:
            The PlanSidePanel instance
        """
        try:
            return app.query_one(cls)
        except NoMatches:
            content_area = app.query_one("#content_area", Horizontal)
            panel = cls()
            content_area.mount(panel)
            return panel

    @classmethod
    def toggle(cls, app: App) -> None:
        """Toggle the Plan side panel on/off within the given app."""
        try:
            app.query_one(cls).remove()
        except NoMatches:
            cls.get_or_create(app)

    def compose(self):
        """Compose the Plan side panel content."""
        yield Static("Agent Plan", classes="plan-header")
        yield Static("", id="plan-content")

    def on_mount(self):
        """Called when the panel is mounted."""
        self._refresh_content()

    @staticmethod
    def _load_tasks_from_path(
        persistence_dir: str | Path | None,
    ) -> list[TaskItem] | None:
        """Load tasks from the TASKS.json file in the given persistence directory.

        The TaskTrackerExecutor saves tasks to TASKS.json in the conversation's
        persistence directory. This method reads from that file directly.

        Args:
            persistence_dir: Path to the conversation's persistence directory

        Returns:
            List of TaskItem objects if a plan exists, None otherwise
        """
        if not persistence_dir:
            return None

        tasks_file = Path(persistence_dir) / "TASKS.json"
        if not tasks_file.exists():
            return None

        try:
            with open(tasks_file, encoding="utf-8") as f:
                return [TaskItem.model_validate(d) for d in json.load(f)]
        except (OSError, json.JSONDecodeError, TypeError, ValidationError):
            return None

    def _refresh_content(self):
        """Refresh the plan content display."""
        content_widget = self.query_one("#plan-content", Static)

        if not self._task_list:
            content_widget.update(
                f"[{OPENHANDS_THEME.foreground}]No plan available yet.\n"
                f"The agent will create a plan when it starts working."
                f"[/{OPENHANDS_THEME.foreground}]"
            )
            return

        # Build content string with task items
        content_parts = []

        for task in self._task_list:
            icon = STATUS_ICONS.get(task.status, "○")

            # Get color based on status
            if task.status == "done":
                color = OPENHANDS_THEME.success
            elif task.status == "in_progress":
                color = OPENHANDS_THEME.warning
            else:
                color = OPENHANDS_THEME.foreground

            # Format task line
            task_line = f"[{color}]{icon} {task.title}[/{color}]"
            content_parts.append(task_line)

            # Add notes if present (indented)
            if task.notes:
                notes_line = (
                    f"  [{OPENHANDS_THEME.foreground} 70%]"
                    f"{task.notes}[/{OPENHANDS_THEME.foreground} 70%]"
                )
                content_parts.append(notes_line)

        # Add summary at the bottom
        done_count = sum(1 for t in self._task_list if t.status == "done")
        in_progress_count = sum(1 for t in self._task_list if t.status == "in_progress")
        total = len(self._task_list)

        content_parts.append("")  # Empty line before summary
        summary = (
            f"[{OPENHANDS_THEME.accent}]"
            f"Progress: {done_count}/{total} done"
            f"[/{OPENHANDS_THEME.accent}]"
        )
        if in_progress_count > 0:
            summary += (
                f" [{OPENHANDS_THEME.warning}]"
                f"({in_progress_count} in progress)"
                f"[/{OPENHANDS_THEME.warning}]"
            )

        content_parts.append(summary)

        content_text = "\n".join(content_parts)
        content_widget.update(content_text)
