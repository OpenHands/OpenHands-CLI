"""Snapshot tests for OpenHands CLI Textual application.

These tests use pytest-textual-snapshot to capture and compare SVG screenshots
of the application at various states. This helps detect visual regressions
and provides a way to debug the UI.

To update snapshots when intentional changes are made:
    pytest tests/snapshots/ --snapshot-update

To run these tests:
    pytest tests/snapshots/

For more information:
    https://github.com/Textualize/pytest-textual-snapshot
"""

from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Static

from openhands.tools.task_tracker.definition import TaskItem
from openhands_cli.tui.modals.exit_modal import ExitConfirmationModal
from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel


if TYPE_CHECKING:
    pass


class TestExitModalSnapshots:
    """Snapshot tests for the ExitConfirmationModal."""

    def test_exit_modal_initial_state(self, snap_compare):
        """Snapshot test for exit confirmation modal initial state."""

        class ExitModalTestApp(App):
            CSS = """
            Screen {
                align: center middle;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Background content")
                yield Footer()

            def on_mount(self) -> None:
                self.push_screen(ExitConfirmationModal())

        assert snap_compare(ExitModalTestApp(), terminal_size=(80, 24))


class TestPlanSidePanelSnapshots:
    """Snapshot tests for the PlanSidePanel."""

    def test_plan_panel_empty_state(self, snap_compare):
        """Snapshot test for plan panel with no tasks."""

        class PlanPanelTestApp(App):
            CSS = """
            Screen {
                layout: horizontal;
            }
            #main_content {
                width: 2fr;
            }
            """

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.conversation_dir = ""
                self.plan_panel: PlanSidePanel | None = None

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content area", id="main_content")
                yield Footer()

            def on_mount(self) -> None:
                self.plan_panel = PlanSidePanel(self)  # type: ignore[arg-type]
                # Toggle to show the panel
                self.plan_panel.toggle()

        assert snap_compare(PlanPanelTestApp(), terminal_size=(100, 30))

    def test_plan_panel_with_tasks(self, snap_compare):
        """Snapshot test for plan panel with various task states."""
        task_list = [
            TaskItem(title="Analyze codebase structure", notes="", status="done"),
            TaskItem(title="Implement feature X", notes="", status="in_progress"),
            TaskItem(
                title="Write unit tests",
                notes="Focus on edge cases",
                status="todo",
            ),
            TaskItem(title="Update documentation", notes="", status="todo"),
        ]

        class PlanPanelWithTasksApp(App):
            CSS = """
            Screen {
                layout: horizontal;
            }
            #main_content {
                width: 2fr;
            }
            """

            def __init__(self, tasks: list[TaskItem], **kwargs):
                super().__init__(**kwargs)
                self.conversation_dir = ""
                self.plan_panel: PlanSidePanel | None = None
                self._tasks = tasks

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content area", id="main_content")
                yield Footer()

            def on_mount(self) -> None:
                self.plan_panel = PlanSidePanel(self)  # type: ignore[arg-type]
                self.plan_panel._task_list = self._tasks
                # Toggle to show the panel
                self.plan_panel.toggle()

        assert snap_compare(
            PlanPanelWithTasksApp(tasks=task_list), terminal_size=(100, 30)
        )

    def test_plan_panel_all_done(self, snap_compare):
        """Snapshot test for plan panel with all tasks completed."""
        task_list = [
            TaskItem(title="Task 1", notes="", status="done"),
            TaskItem(title="Task 2", notes="", status="done"),
            TaskItem(title="Task 3", notes="", status="done"),
        ]

        class PlanPanelAllDoneApp(App):
            CSS = """
            Screen {
                layout: horizontal;
            }
            #main_content {
                width: 2fr;
            }
            """

            def __init__(self, tasks: list[TaskItem], **kwargs):
                super().__init__(**kwargs)
                self.conversation_dir = ""
                self.plan_panel: PlanSidePanel | None = None
                self._tasks = tasks

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content area", id="main_content")
                yield Footer()

            def on_mount(self) -> None:
                self.plan_panel = PlanSidePanel(self)  # type: ignore[arg-type]
                self.plan_panel._task_list = self._tasks
                # Toggle to show the panel
                self.plan_panel.toggle()

        assert snap_compare(
            PlanPanelAllDoneApp(tasks=task_list), terminal_size=(100, 30)
        )
