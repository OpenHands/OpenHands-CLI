"""Tests for event utility functions in utils.py."""

import pytest
import streamingjson

from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.task_tracker import TaskTrackerAction
from openhands.tools.terminal import TerminalAction
from openhands_cli.acp_impl.events.utils import (
    format_content_blocks,
    get_tool_kind,
    get_tool_title,
)


class TestGetToolKind:
    """Tests for get_tool_kind function."""

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
        ],
    )
    def test_tool_kind_by_name(self, tool_name: str, expected: str):
        """Test tool kind mapping for various tool names."""
        result = get_tool_kind(tool_name)
        assert result == expected

    def test_file_editor_view_action(self):
        """Test file_editor with view command returns 'read'."""
        action = FileEditorAction(command="view", path="/test.py")
        result = get_tool_kind("file_editor", action=action)
        assert result == "read"

    @pytest.mark.parametrize("command", ["str_replace", "create", "insert", "undo_edit"])
    def test_file_editor_edit_actions(self, command: str):
        """Test file_editor with edit commands returns 'edit'."""
        action = FileEditorAction(command=command, path="/test.py")
        result = get_tool_kind("file_editor", action=action)
        assert result == "edit"

    def test_file_editor_streaming_view(self):
        """Test file_editor with streaming partial args for view command."""
        lexer = streamingjson.Lexer()
        lexer.append_string('{"command": "view", "path": "/test.py"}')
        result = get_tool_kind("file_editor", partial_args=lexer)
        assert result == "read"

    def test_file_editor_streaming_edit(self):
        """Test file_editor with streaming partial args for non-view command."""
        lexer = streamingjson.Lexer()
        lexer.append_string('{"command": "str_replace", "path": "/test.py"}')
        result = get_tool_kind("file_editor", partial_args=lexer)
        assert result == "edit"

    def test_file_editor_streaming_incomplete(self):
        """Test file_editor with incomplete streaming args defaults to 'edit'."""
        lexer = streamingjson.Lexer()
        lexer.append_string('{"comma')  # Incomplete JSON
        result = get_tool_kind("file_editor", partial_args=lexer)
        assert result == "edit"

    def test_file_editor_no_args_defaults_other(self):
        """Test file_editor without action or partial_args returns from mapping."""
        result = get_tool_kind("file_editor")
        assert result == "other"  # Falls through to TOOL_KIND_MAPPING.get


class TestGetToolTitle:
    """Tests for get_tool_title function."""

    def test_task_tracker_always_plan_updated(self):
        """Test task_tracker always returns 'Plan updated'."""
        result = get_tool_title("task_tracker")
        assert result == "Plan updated"

    def test_file_editor_view_action(self):
        """Test file_editor view action generates 'Reading' title."""
        action = FileEditorAction(command="view", path="/src/main.py")
        result = get_tool_title("file_editor", action=action)
        assert result == "Reading /src/main.py"

    @pytest.mark.parametrize(
        "command,path",
        [
            ("str_replace", "/src/main.py"),
            ("create", "/new/file.txt"),
            ("insert", "/code.py"),
        ],
    )
    def test_file_editor_edit_actions(self, command: str, path: str):
        """Test file_editor edit actions generate 'Editing' title."""
        action = FileEditorAction(command=command, path=path)
        result = get_tool_title("file_editor", action=action)
        assert result == f"Editing {path}"

    def test_terminal_action(self):
        """Test terminal action uses command as title."""
        action = TerminalAction(command="git status")
        result = get_tool_title("terminal", action=action)
        assert result == "git status"

    def test_task_tracker_action(self):
        """Test TaskTrackerAction returns 'Plan updated'."""
        action = TaskTrackerAction(command="plan", task_list=[])
        result = get_tool_title("task_tracker", action=action)
        assert result == "Plan updated"

    def test_streaming_file_editor_view(self):
        """Test file_editor streaming args with view command."""
        lexer = streamingjson.Lexer()
        lexer.append_string('{"command": "view", "path": "/test.py"}')
        result = get_tool_title("file_editor", partial_args=lexer)
        assert result == "Reading /test.py"

    def test_streaming_file_editor_edit(self):
        """Test file_editor streaming args with edit command."""
        lexer = streamingjson.Lexer()
        lexer.append_string('{"command": "str_replace", "path": "/test.py"}')
        result = get_tool_title("file_editor", partial_args=lexer)
        assert result == "Editing /test.py"

    def test_streaming_terminal(self):
        """Test terminal streaming args extracts command."""
        lexer = streamingjson.Lexer()
        lexer.append_string('{"command": "ls -la"}')
        result = get_tool_title("terminal", partial_args=lexer)
        assert result == "ls -la"

    def test_no_args_returns_empty(self):
        """Test unknown tool without args returns empty string."""
        result = get_tool_title("unknown_tool")
        assert result == ""

    def test_streaming_incomplete_json(self):
        """Test incomplete JSON falls back to tool_name."""
        lexer = streamingjson.Lexer()
        lexer.append_string('{"incomplete')
        result = get_tool_title("file_editor", partial_args=lexer)
        # When args are incomplete, falls back to tool_name
        assert result == "file_editor"


class TestFormatContentBlocks:
    """Tests for format_content_blocks function."""

    def test_format_text(self):
        """Test formatting text into content blocks."""
        result = format_content_blocks("Hello, world!")
        assert result is not None
        assert len(result) == 1
        # ContentToolCallContent has 'content' which contains the text block
        assert result[0].content.text == "Hello, world!"

    def test_format_empty_string(self):
        """Test empty string returns None."""
        result = format_content_blocks("")
        assert result is None

    def test_format_whitespace_only(self):
        """Test whitespace-only string returns None."""
        result = format_content_blocks("   \n\t  ")
        assert result is None

    def test_format_none(self):
        """Test None input returns None."""
        result = format_content_blocks(None)
        assert result is None
