"""Tests for event utility functions in utils.py.

Note: Streaming partial_args handling for kind/title has been moved to
ToolCallState. See test_tool_state.py for those tests.
"""

from __future__ import annotations

import pytest

from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.task_tracker import TaskTrackerAction
from openhands.tools.terminal import TerminalAction
from openhands_cli.acp_impl.events.utils import (
    format_content_blocks,
    get_tool_kind,
    get_tool_title,
)


class TestGetToolKind:
    @pytest.mark.parametrize(
        "tool_name,expected",
        [
            ("think", "think"),
            ("browser", "fetch"),
            ("browser_use", "fetch"),
            ("browser_navigate", "fetch"),
            ("terminal", "execute"),
            ("unknown_tool", "other"),
            ("custom_tool", "other"),
            ("file_editor", "other"),  # falls back to mapping default if no action
        ],
    )
    def test_tool_kind_by_name_only(self, tool_name: str, expected: str):
        assert get_tool_kind(tool_name) == expected

    @pytest.mark.parametrize(
        "command,expected",
        [
            ("view", "read"),
            ("str_replace", "edit"),
            ("create", "edit"),
            ("insert", "edit"),
            ("undo_edit", "edit"),
        ],
    )
    def test_file_editor_kind_from_action(self, command: str, expected: str):
        action = FileEditorAction(command=command, path="/test.py")  # type: ignore[arg-type]
        assert get_tool_kind("file_editor", action=action) == expected


class TestGetToolTitle:
    def test_task_tracker_title_constant(self):
        assert get_tool_title("task_tracker") == "Plan updated"

    @pytest.mark.parametrize(
        "action,expected",
        [
            (
                FileEditorAction(command="view", path="/src/main.py"),
                "Reading /src/main.py",
            ),
            (
                FileEditorAction(command="str_replace", path="/src/main.py"),
                "Editing /src/main.py",
            ),
            (TerminalAction(command="git status"), "git status"),
            (TaskTrackerAction(command="plan", task_list=[]), "Plan updated"),
        ],
    )
    def test_title_from_action(self, action, expected: str):
        tool_name = (
            "file_editor"
            if isinstance(action, FileEditorAction)
            else "terminal"
            if isinstance(action, TerminalAction)
            else "task_tracker"
        )
        assert get_tool_title(tool_name, action=action) == expected

    @pytest.mark.parametrize("tool_name", ["unknown_tool", "terminal", "file_editor"])
    def test_title_no_action_returns_empty(self, tool_name: str):
        assert get_tool_title(tool_name) == ""


class TestFormatContentBlocks:
    @pytest.mark.parametrize(
        "text,expected_none",
        [
            (None, True),
            ("", True),
            ("   \n\t  ", True),
            ("Hello, world!", False),
        ],
    )
    def test_format_content_blocks(self, text: str | None, expected_none: bool):
        result = format_content_blocks(text)
        if expected_none:
            assert result is None
            return

        assert result is not None
        assert len(result) == 1
        assert result[0].content.text == "Hello, world!"
