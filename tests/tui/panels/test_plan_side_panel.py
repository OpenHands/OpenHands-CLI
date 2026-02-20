"""Tests for PlanSidePanel widget."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from openhands.tools.task_tracker.definition import TaskItem
from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel


if TYPE_CHECKING:
    pass


def _create_mock_app(conversation_dir: str | Path | None = None) -> Any:
    """Create a mock OpenHandsApp with required attributes."""
    mock_app = MagicMock()
    mock_app.conversation_dir = str(conversation_dir) if conversation_dir else ""
    mock_app.query_one = MagicMock()
    return mock_app


# ============================================================================
# Test App Helper
# ============================================================================


class PlanPanelTestApp(App):
    """Test app for mounting PlanSidePanel."""

    CSS = """
    Screen { layout: horizontal; }
    #main_content { width: 2fr; }
    """

    def __init__(self, conversation_dir: str | Path | None = None, **kwargs):
        super().__init__(**kwargs)
        self.conversation_dir = str(conversation_dir) if conversation_dir else ""
        self.plan_panel: PlanSidePanel | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="content_area"):
            yield Static("Main content", id="main_content")

    def on_mount(self) -> None:
        self.plan_panel = PlanSidePanel(self)  # type: ignore[arg-type]


# ============================================================================
# _load_tasks Tests (instance method)
# ============================================================================


class TestLoadTasks:
    """Tests for PlanSidePanel._load_tasks instance method."""

    def test_returns_none_when_no_conversation_dir(self):
        """Verify _load_tasks returns None when conversation_dir is empty."""
        mock_app = _create_mock_app("")
        panel = PlanSidePanel(mock_app)
        result = panel._load_tasks()
        assert result is None

    def test_returns_none_when_file_missing(self, tmp_path: Path):
        """Verify returns None when TASKS.json doesn't exist."""
        mock_app = _create_mock_app(tmp_path)
        panel = PlanSidePanel(mock_app)
        result = panel._load_tasks()
        assert result is None

    @pytest.mark.parametrize(
        "invalid_content",
        [
            "not valid json",
            "{malformed",
            "['unclosed array",
        ],
    )
    def test_returns_none_on_invalid_json(self, tmp_path: Path, invalid_content: str):
        """Verify returns None when TASKS.json contains malformed JSON."""
        tasks_file = tmp_path / "TASKS.json"
        tasks_file.write_text(invalid_content)

        mock_app = _create_mock_app(tmp_path)
        panel = PlanSidePanel(mock_app)
        result = panel._load_tasks()
        assert result is None

    @pytest.mark.parametrize(
        "invalid_task_data",
        [
            [{"status": "done"}],  # Missing title (required field)
            [{"title": "Task 1", "status": "invalid_status"}],  # Invalid status value
            [{"title": 123, "status": "done"}],  # Wrong type for title
        ],
    )
    def test_returns_none_on_validation_error(
        self, tmp_path: Path, invalid_task_data: list
    ):
        """Verify returns None when TASKS.json contains invalid TaskItem data."""
        tasks_file = tmp_path / "TASKS.json"
        tasks_file.write_text(json.dumps(invalid_task_data))

        mock_app = _create_mock_app(tmp_path)
        panel = PlanSidePanel(mock_app)
        result = panel._load_tasks()
        assert result is None

    @pytest.mark.parametrize(
        "tasks_data,expected_count",
        [
            ([], 0),
            ([{"title": "Task 1", "status": "todo"}], 1),
            (
                [
                    {"title": "Task 1", "status": "done"},
                    {"title": "Task 2", "status": "in_progress"},
                    {"title": "Task 3", "status": "todo", "notes": "Some notes"},
                ],
                3,
            ),
        ],
    )
    def test_parses_valid_tasks(
        self, tmp_path: Path, tasks_data: list, expected_count: int
    ):
        """Verify correct parsing of valid TASKS.json into TaskItem list."""
        tasks_file = tmp_path / "TASKS.json"
        tasks_file.write_text(json.dumps(tasks_data))

        mock_app = _create_mock_app(tmp_path)
        panel = PlanSidePanel(mock_app)
        result = panel._load_tasks()

        assert result is not None
        assert len(result) == expected_count
        for i, task in enumerate(result):
            assert isinstance(task, TaskItem)
            assert task.title == tasks_data[i]["title"]
            assert task.status == tasks_data[i]["status"]


# ============================================================================
# toggle Tests
# ============================================================================


class TestToggle:
    """Tests for PlanSidePanel.toggle instance method."""

    @pytest.mark.asyncio
    async def test_mounts_panel_when_not_on_screen(self, tmp_path: Path):
        """Verify toggle() mounts the panel and marks it as on_screen."""
        app = PlanPanelTestApp(conversation_dir=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()  # Wait for on_mount

            # Verify panel exists but is not mounted
            assert app.plan_panel is not None
            assert app.plan_panel.is_on_screen is False

            # Mock refresh_from_disk to avoid compose timing issues
            with patch.object(app.plan_panel, "refresh_from_disk"):
                # Toggle to mount - this mounts the panel
                app.plan_panel.toggle()
                await pilot.pause()

                # Verify panel is now mounted
                assert app.plan_panel.is_on_screen is True

    @pytest.mark.asyncio
    async def test_removes_panel_when_on_screen(self, tmp_path: Path):
        """Verify toggle() removes an existing panel."""
        app = PlanPanelTestApp(conversation_dir=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()  # Wait for on_mount
            assert app.plan_panel is not None

            # Mock refresh_from_disk for first toggle
            with patch.object(app.plan_panel, "refresh_from_disk"):
                app.plan_panel.toggle()
                await pilot.pause()
                assert app.plan_panel.is_on_screen is True

            # Toggle to remove (no refresh needed when removing)
            app.plan_panel.toggle()
            await pilot.pause()

            # Verify panel is removed
            assert app.plan_panel.is_on_screen is False

    @pytest.mark.asyncio
    async def test_toggle_sets_user_dismissed_flag(self, tmp_path: Path):
        """Verify toggle() sets user_dismissed flag when removing panel."""
        app = PlanPanelTestApp(conversation_dir=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.plan_panel is not None

            # Mount the panel first
            with patch.object(app.plan_panel, "refresh_from_disk"):
                app.plan_panel.toggle()
                await pilot.pause()

            # Verify user_dismissed is initially False
            assert app.plan_panel.user_dismissed is False

            # Toggle to remove
            app.plan_panel.toggle()
            await pilot.pause()

            # Verify user_dismissed is now True
            assert app.plan_panel.user_dismissed is True


# ============================================================================
# refresh_from_disk Tests
# ============================================================================


class TestRefreshFromDisk:
    """Tests for PlanSidePanel.refresh_from_disk method."""

    def test_loads_tasks_and_updates_task_list(self, tmp_path: Path):
        """Verify refresh_from_disk loads tasks from conversation directory."""
        # Create tasks file
        tasks_data = [{"title": "New Task", "status": "in_progress"}]
        tasks_file = tmp_path / "TASKS.json"
        tasks_file.write_text(json.dumps(tasks_data))

        mock_app = _create_mock_app(tmp_path)
        panel = PlanSidePanel(mock_app)

        # Initially no tasks
        assert panel.task_list == []

        # Mock _refresh_content since panel is not composed
        with patch.object(panel, "_refresh_content"):
            panel.refresh_from_disk()

        # Verify tasks were loaded
        assert len(panel.task_list) == 1
        assert panel.task_list[0].title == "New Task"
        assert panel.task_list[0].status == "in_progress"

    def test_clears_tasks_when_file_missing(self, tmp_path: Path):
        """Verify refresh_from_disk clears tasks when file doesn't exist."""
        mock_app = _create_mock_app(tmp_path)
        panel = PlanSidePanel(mock_app)

        # Pre-populate task list
        panel._task_list = [TaskItem(title="Old Task", notes="", status="done")]

        # Mock _refresh_content since panel is not composed
        with patch.object(panel, "_refresh_content"):
            panel.refresh_from_disk()

        # Verify tasks were cleared
        assert panel.task_list == []

    def test_calls_refresh_content(self, tmp_path: Path):
        """Verify refresh_from_disk calls _refresh_content."""
        mock_app = _create_mock_app(tmp_path)
        panel = PlanSidePanel(mock_app)

        with patch.object(panel, "_refresh_content") as mock_refresh:
            panel.refresh_from_disk()
            mock_refresh.assert_called_once()
