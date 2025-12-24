"""Tests for event utility functions in utils.py."""

from __future__ import annotations

import pytest
from streamingjson import Lexer

from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.task_tracker import TaskTrackerAction
from openhands.tools.terminal import TerminalAction
from openhands_cli.acp_impl.events.utils import (
    format_content_blocks,
    get_tool_kind,
    get_tool_title,
)


def _lexer(s: str) -> Lexer:
    lex = Lexer()
    lex.append_string(s)
    return lex


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
            ("file_editor", "other"),  # falls back to mapping default if no args/action
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
        "partial_json,expected",
        [
            # "view" should be detectable even if the JSON is truncated
            ('{"command":"view","path":"/te', "read"),
            # non-view / unknown command should default to edit
            ('{"command":"str_rep', "edit"),
            # totally borked => parse error => default edit
            ('{"comma', "edit"),
        ],
    )
    def test_file_editor_kind_from_streaming_partial_args(
        self, partial_json: str, expected: str
    ):
        assert (
            get_tool_kind("file_editor", partial_args=_lexer(partial_json)) == expected
        )


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

    @pytest.mark.parametrize(
        "tool_name,partial_json,expected",
        [
            # file_editor, truncated but still enough to parse and extract fields
            ("file_editor", '{"command":"view","path":"/test.py"', "Reading /test.py"),
            (
                "file_editor",
                '{"command":"str_replace","path":"/test.py"',
                "Editing /test.py",
            ),
            # terminal, truncated but parseable enough
            ("terminal", '{"command":"ls -la"', "ls -la"),
            # file_editor missing/empty path => falls through to tool_name
            ("file_editor", '{"command":"view"', "file_editor"),
            ("file_editor", '{"command":"view","path":""', "file_editor"),
            # parses but not a dict => returns tool_name
            (
                "file_editor",
                "[",
                "file_editor",
            ),  # Lexer may complete to [] depending on impl
            ("terminal", "[]", "terminal"),  # guaranteed non-dict parse
        ],
    )
    def test_title_from_streaming_partial_args(
        self, tool_name: str, partial_json: str, expected: str
    ):
        assert get_tool_title(tool_name, partial_args=_lexer(partial_json)) == expected

    @pytest.mark.parametrize(
        "tool_name,partial_json",
        [
            ("terminal", '{""command"'),  # parse error => ""
            ("file_editor", "{'}'"),  # parse error => ""
        ],
    )
    def test_title_streaming_parse_error_returns_empty(
        self, tool_name: str, partial_json: str
    ):
        assert get_tool_title(tool_name, partial_args=_lexer(partial_json)) == ""

    @pytest.mark.parametrize("tool_name", ["unknown_tool", "terminal", "file_editor"])
    def test_title_no_partial_args_and_no_action_returns_empty(self, tool_name: str):
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
