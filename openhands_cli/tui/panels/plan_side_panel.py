"""Plan side panel widget for displaying agent task plan."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError
from rich.markup import escape
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Static

from openhands.tools.task_tracker.definition import (
    TaskItem,
    TaskTrackerStatusType,
)
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.panels.plan_panel_style import PLAN_PANEL_STYLE


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


logger = logging.getLogger(__name__)

# Status icons for visual representation
STATUS_ICONS: dict[TaskTrackerStatusType, str] = {
    "todo": "⏳",
    "in_progress": "🔄",
    "done": "✅",
}

# Status colors for visual representation
STATUS_COLORS: dict[TaskTrackerStatusType, str | None] = {
    "done": OPENHANDS_THEME.success,
    "in_progress": OPENHANDS_THEME.warning,
}


class PlanSidePanel(VerticalScroll):
    """Side panel widget that displays the agent's task plan.

    This panel is self-sufficient - it knows its persistence directory and can
    reload tasks from disk when needed. External callers just need to call
    refresh_from_disk() to trigger an update.
    """

    DEFAULT_CSS = PLAN_PANEL_STYLE

    def __init__(self, app: OpenHandsApp, **kwargs):
        """Initialize the Plan side panel."""
        super().__init__(**kwargs)
        self._task_list: list[TaskItem] = []
        self._oh_app = app
        self.user_dismissed = False

    @property
    def task_list(self) -> list[TaskItem]:
        """Get the current task list."""
        return self._task_list

    def refresh_from_disk(self) -> None:
        """Reload tasks from the persistence directory and update display.

        This method reads the TASKS.json file from the persistence directory
        and updates the panel's content. It's safe to call even if no
        persistence directory is set or if the file doesn't exist.
        """
        self._task_list = self._load_tasks() or []
        self._refresh_content()

    def toggle(self) -> None:
        """Toggle the Plan side panel on/off within the given app."""
        if self.is_on_screen:
            self.remove()
            self.user_dismissed = True
        else:
            content_area = self._oh_app.query_one("#content_area", Horizontal)
            content_area.mount(self)
            self.refresh_from_disk()

    def compose(self):
        """Compose the Plan side panel content."""
        with Horizontal(classes="plan-header-row"):
            yield Static("Agent Plan", classes="plan-header")
            yield Button("✕", id="plan-close-btn", classes="plan-close-btn")
        yield Static("", id="plan-content")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "plan-close-btn":
            self.toggle()

    def _load_tasks(self) -> list[TaskItem] | None:
        """Load tasks from the TASKS.json file in the conversation directory.

        The TaskTrackerExecutor saves tasks to TASKS.json in the conversation's
        persistence directory. This method reads from that file directly.

        Returns:
            List of TaskItem objects if a plan exists, None otherwise
        """
        tasks_file = Path(self._oh_app.conversation_dir) / "TASKS.json"
        if not tasks_file.exists():
            return None

        try:
            with open(tasks_file, encoding="utf-8") as f:
                return [TaskItem.model_validate(d) for d in json.load(f)]
        except (OSError, json.JSONDecodeError, TypeError, ValidationError) as e:
            logger.warning("Failed to load tasks from %s: %s", tasks_file, e)
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
            color = STATUS_COLORS.get(task.status, OPENHANDS_THEME.foreground)

            # Escape user-provided content to prevent markup injection
            title = escape(task.title)

            # Format task line
            task_line = f"[{color}]{icon} {title}[/{color}]"
            content_parts.append(task_line)

            # Add notes if present (indented)
            if task.notes:
                notes = escape(task.notes)
                notes_line = (
                    f"  [{OPENHANDS_THEME.foreground} 70%]"
                    f"{notes}[/{OPENHANDS_THEME.foreground} 70%]"
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
