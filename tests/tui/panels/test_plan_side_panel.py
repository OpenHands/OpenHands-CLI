"""Tests for PlanSidePanel widget."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.widgets import Static

from openhands.tools.task_tracker.definition import TaskItem
from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel


# ============================================================================
# Test App Helper
# ============================================================================


class PlanPanelTestApp(App):
    """Test app for mounting PlanSidePanel."""

    CSS = """
    Screen { layout: horizontal; }
    #main_content { width: 2fr; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="content_area"):
            yield Static("Main content", id="main_content")


# ============================================================================
# _load_tasks_from_path Tests
# ============================================================================


class TestLoadTasksFromPath:
    """Tests for PlanSidePanel._load_tasks_from_path static method."""

    @pytest.mark.parametrize(
        "persistence_dir",
        [None, ""],
    )
    def test_returns_none_when_no_persistence_dir(self, persistence_dir):
        """Verify _load_tasks_from_path returns None when path is None or empty."""
        result = PlanSidePanel._load_tasks_from_path(persistence_dir)
        assert result is None

    def test_returns_none_when_file_missing(self, tmp_path: Path):
        """Verify returns None when TASKS.json doesn't exist."""
        result = PlanSidePanel._load_tasks_from_path(tmp_path)
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

        result = PlanSidePanel._load_tasks_from_path(tmp_path)
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

        result = PlanSidePanel._load_tasks_from_path(tmp_path)
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

        result = PlanSidePanel._load_tasks_from_path(tmp_path)

        assert result is not None
        assert len(result) == expected_count
        for i, task in enumerate(result):
            assert isinstance(task, TaskItem)
            assert task.title == tasks_data[i]["title"]
            assert task.status == tasks_data[i]["status"]


# ============================================================================
# set_persistence_dir Tests
# ============================================================================


class TestSetPersistenceDir:
    """Tests for PlanSidePanel.set_persistence_dir method."""

    @pytest.mark.asyncio
    async def test_triggers_refresh_and_loads_tasks(self, tmp_path: Path):
        """Verify calling set_persistence_dir() loads tasks and updates content."""
        # Create tasks file
        tasks_data = [{"title": "Test Task", "status": "todo"}]
        tasks_file = tmp_path / "TASKS.json"
        tasks_file.write_text(json.dumps(tasks_data))

        class TestApp(App):
            CSS = """
            Screen { layout: horizontal; }
            #main_content { width: 2fr; }
            """

            def compose(self):
                with Horizontal(id="content_area"):
                    yield Static("Main content", id="main_content")
                    yield PlanSidePanel()

        app = TestApp()
        async with app.run_test():
            panel = app.query_one(PlanSidePanel)

            # Initially no tasks
            assert panel.task_list == []
            assert panel.persistence_dir is None

            # Set persistence dir
            panel.set_persistence_dir(tmp_path)

            assert panel.persistence_dir == tmp_path
            assert len(panel.task_list) == 1
            assert panel.task_list[0].title == "Test Task"


# ============================================================================
# toggle Tests
# ============================================================================


class TestToggle:
    """Tests for PlanSidePanel.toggle class method."""

    @pytest.mark.asyncio
    async def test_creates_panel_when_not_exists(self):
        """Verify toggle() creates and mounts a new panel when none exists."""
        app = PlanPanelTestApp()
        async with app.run_test() as pilot:
            # Verify no panel exists
            with pytest.raises(NoMatches):
                app.query_one(PlanSidePanel)

            # Toggle to create
            PlanSidePanel.toggle(app)
            await pilot.pause()

            # Verify panel now exists
            panel = app.query_one(PlanSidePanel)
            assert panel is not None

    @pytest.mark.asyncio
    async def test_removes_panel_when_exists(self):
        """Verify toggle() removes an existing panel."""
        app = PlanPanelTestApp()
        async with app.run_test() as pilot:
            # Create panel first
            PlanSidePanel.toggle(app)
            await pilot.pause()
            assert app.query_one(PlanSidePanel) is not None

            # Toggle to remove
            PlanSidePanel.toggle(app)
            await pilot.pause()

            # Verify panel is removed
            with pytest.raises(NoMatches):
                app.query_one(PlanSidePanel)


# ============================================================================
# get_or_create Tests
# ============================================================================


class TestGetOrCreate:
    """Tests for PlanSidePanel.get_or_create class method."""

    @pytest.mark.asyncio
    async def test_returns_existing_panel(self):
        """Verify returns existing panel instance without creating new one."""
        app = PlanPanelTestApp()
        async with app.run_test() as pilot:
            # Create panel first
            first_panel = PlanSidePanel.get_or_create(app)
            await pilot.pause()

            # Get again - should return same instance
            second_panel = PlanSidePanel.get_or_create(app)

            assert first_panel is second_panel

    @pytest.mark.asyncio
    async def test_creates_new_panel_when_missing(self):
        """Verify creates and mounts a new panel when none exists."""
        app = PlanPanelTestApp()
        async with app.run_test() as pilot:
            # Verify no panel exists
            with pytest.raises(NoMatches):
                app.query_one(PlanSidePanel)

            # Get or create
            panel = PlanSidePanel.get_or_create(app)
            await pilot.pause()

            # Verify panel exists and is the same instance
            queried_panel = app.query_one(PlanSidePanel)
            assert panel is queried_panel


# ============================================================================
# refresh_from_disk Tests
# ============================================================================


class TestRefreshFromDisk:
    """Tests for PlanSidePanel.refresh_from_disk method."""

    @pytest.mark.asyncio
    async def test_updates_task_list_from_file(self, tmp_path: Path):
        """Verify refresh_from_disk reloads tasks from persistence directory."""

        class TestApp(App):
            CSS = """
            Screen { layout: horizontal; }
            #main_content { width: 2fr; }
            """

            def compose(self):
                with Horizontal(id="content_area"):
                    yield Static("Main content", id="main_content")
                    yield PlanSidePanel()

        app = TestApp()
        async with app.run_test():
            panel = app.query_one(PlanSidePanel)
            panel._persistence_dir = tmp_path

            # Initially no tasks file
            assert panel.task_list == []

            # Create tasks file
            tasks_data = [{"title": "New Task", "status": "in_progress"}]
            tasks_file = tmp_path / "TASKS.json"
            tasks_file.write_text(json.dumps(tasks_data))

            # Refresh from disk
            panel.refresh_from_disk()

            assert len(panel.task_list) == 1
            assert panel.task_list[0].title == "New Task"
            assert panel.task_list[0].status == "in_progress"

    @pytest.mark.asyncio
    async def test_safe_when_no_persistence_dir(self):
        """Verify refresh_from_disk is safe to call with no persistence dir."""

        class TestApp(App):
            CSS = """
            Screen { layout: horizontal; }
            #main_content { width: 2fr; }
            """

            def compose(self):
                with Horizontal(id="content_area"):
                    yield Static("Main content", id="main_content")
                    yield PlanSidePanel()

        app = TestApp()
        async with app.run_test():
            panel = app.query_one(PlanSidePanel)

            # Should not raise
            panel.refresh_from_disk()
            assert panel.task_list == []
