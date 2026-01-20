"""Tests for event utility functions in utils.py.

Note: Streaming partial_args handling for kind/title has been moved to
ToolCallState. See test_tool_state.py for those tests.
"""

from __future__ import annotations

import pytest

from openhands.tools.delegate.definition import DelegateAction
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

    @pytest.mark.parametrize(
        "delegate_command",
        ["spawn", "delegate"],
    )
    def test_delegate_kind_from_action(self, delegate_command: str):
        """DelegateAction always returns 'other' kind regardless of command."""
        action = DelegateAction(command=delegate_command)  # type: ignore[arg-type]
        assert get_tool_kind("delegate", action=action) == "other"


class TestGetToolTitle:
    def test_task_tracker_title_empty_without_action(self):
        assert get_tool_title("task_tracker") == ""

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
            (TerminalAction(command="git status"), "$ git status"),
            (TaskTrackerAction(command="plan", task_list=[]), ""),
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

    @pytest.mark.parametrize(
        "action,expected",
        [
            (
                DelegateAction(command="spawn", ids=["agent1", "agent2"]),
                "Spawning 2 sub-agent(s): agent1, agent2",
            ),
            (
                DelegateAction(command="spawn"),
                "Spawning sub-agents",
            ),
            (
                DelegateAction(command="delegate", tasks={"a": "t1", "b": "t2"}),
                "Delegating 2 task(s) to: a, b",
            ),
            (
                DelegateAction(command="delegate"),
                "Delegating tasks",
            ),
        ],
    )
    def test_delegate_title_from_action(self, action: DelegateAction, expected: str):
        """DelegateAction title depends on command and ids/tasks."""
        assert get_tool_title("delegate", action=action) == expected

    def test_title_with_summary_terminal(self):
        """Test that summary is included in terminal action title."""
        action = TerminalAction(command="git status")
        title = get_tool_title("terminal", action=action, summary="Check git status")
        assert title == "Check git status: $ git status"

    def test_title_with_summary_file_editor_view(self):
        """Test that summary is included in file editor view title."""
        action = FileEditorAction(command="view", path="/src/main.py")
        title = get_tool_title("file_editor", action=action, summary="Read main file")
        assert title == "Read main file: Reading /src/main.py"

    def test_title_with_summary_file_editor_edit(self):
        """Test that summary is included in file editor edit title."""
        action = FileEditorAction(command="str_replace", path="/src/main.py")
        title = get_tool_title("file_editor", action=action, summary="Fix bug in main")
        assert title == "Fix bug in main: Editing /src/main.py"

    def test_title_with_summary_only(self):
        """Test that summary alone is used when no action details available."""
        title = get_tool_title("unknown_tool", summary="Do something important")
        assert title == "Do something important"

    def test_title_with_summary_newlines_stripped(self):
        """Test that newlines in summary are replaced with spaces."""
        action = TerminalAction(command="ls")
        title = get_tool_title(
            "terminal", action=action, summary="List files\nin directory"
        )
        assert title == "List files in directory: $ ls"


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
