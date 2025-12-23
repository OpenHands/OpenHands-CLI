"""Tests for ToolCallState class and streaming utilities."""

import pytest

from openhands_cli.acp_impl.events.tool_state import (
    ToolCallState,
    _title_from_streaming_args,
)


class TestTitleFromStreamingArgs:
    """Tests for _title_from_streaming_args function."""

    @pytest.mark.parametrize(
        "tool_name,args_str,expected",
        [
            # task_tracker always returns "Plan updated"
            ("task_tracker", "{}", "Plan updated"),
            ("task_tracker", '{"task_list": []}', "Plan updated"),
            # file_editor with view command
            (
                "file_editor",
                '{"command": "view", "path": "/test/file.py"}',
                "Reading /test/file.py",
            ),
            # file_editor with other commands (edit)
            (
                "file_editor",
                '{"command": "str_replace", "path": "/src/main.py"}',
                "Editing /src/main.py",
            ),
            (
                "file_editor",
                '{"command": "create", "path": "/new/file.txt"}',
                "Editing /new/file.txt",
            ),
            (
                "file_editor",
                '{"command": "insert", "path": "/code.py"}',
                "Editing /code.py",
            ),
            # file_editor with path only (no command)
            ("file_editor", '{"path": "/file.txt"}', "Editing /file.txt"),
            # file_editor without path
            ("file_editor", '{"command": "view"}', "file_editor"),
            # terminal with command
            ("terminal", '{"command": "ls -la"}', "ls -la"),
            ("terminal", '{"command": "git status"}', "git status"),
            # terminal without command
            ("terminal", "{}", "terminal"),
            # other tools return tool_name
            ("browser", '{"url": "https://example.com"}', "browser"),
            ("browser_use", '{"action": "click"}', "browser_use"),
            ("think", '{"thought": "thinking..."}', "think"),
        ],
    )
    def test_title_from_args(self, tool_name: str, args_str: str, expected: str):
        """Test title generation from streaming args."""
        import streamingjson

        lexer = streamingjson.Lexer()
        lexer.append_string(args_str)
        result = _title_from_streaming_args(tool_name, lexer)
        assert result == expected

    def test_title_from_invalid_json(self):
        """Test title generation with invalid/incomplete JSON falls back."""
        import streamingjson

        lexer = streamingjson.Lexer()
        lexer.append_string('{"incomplete": ')
        # Falls back to tool_name when JSON can't be fully parsed
        result = _title_from_streaming_args("file_editor", lexer)
        assert result == "file_editor"

    def test_title_from_non_dict_json(self):
        """Test title generation when JSON is not a dict returns empty string."""
        import streamingjson

        lexer = streamingjson.Lexer()
        lexer.append_string('"just a string"')
        # streamingjson.complete_json() may produce invalid JSON for non-dict input
        result = _title_from_streaming_args("file_editor", lexer)
        assert result == ""


class TestToolCallState:
    """Tests for ToolCallState class."""

    def test_initialization(self):
        """Test basic initialization of ToolCallState."""
        state = ToolCallState("call-123", "terminal")
        assert state.tool_call_id == "call-123"
        assert state.tool_name == "terminal"
        assert state.is_think is False
        assert state.args == ""
        assert state.started is False

    def test_initialization_think_tool(self):
        """Test that think tool is identified correctly."""
        state = ToolCallState("call-456", "think")
        assert state.is_think is True

    def test_append_args(self):
        """Test appending arguments to state."""
        state = ToolCallState("call-123", "terminal")
        state.append_args('{"comm')
        assert state.args == '{"comm'
        state.append_args('and": "ls"}')
        assert state.args == '{"command": "ls"}'

    def test_title_property_terminal(self):
        """Test title property for terminal tool."""
        state = ToolCallState("call-123", "terminal")
        state.append_args('{"command": "git status"}')
        assert state.title == "git status"

    def test_title_property_file_editor_view(self):
        """Test title property for file_editor view command."""
        state = ToolCallState("call-123", "file_editor")
        state.append_args('{"command": "view", "path": "/test.py"}')
        assert state.title == "Reading /test.py"

    def test_title_property_file_editor_edit(self):
        """Test title property for file_editor edit commands."""
        state = ToolCallState("call-123", "file_editor")
        state.append_args('{"command": "str_replace", "path": "/test.py"}')
        assert state.title == "Editing /test.py"

    def test_title_property_task_tracker(self):
        """Test title property for task_tracker always returns 'Plan updated'."""
        state = ToolCallState("call-123", "task_tracker")
        state.append_args("{}")
        assert state.title == "Plan updated"

    @pytest.mark.parametrize(
        "args_parts,expected_final_thought",
        [
            # Single complete thought
            (['{"thought": "thinking deeply"}'], "thinking deeply"),
            # Incrementally streamed thought
            (['{"thou', 'ght": "hello', ' world"}'], "hello world"),
            # Empty thought
            (['{"thought": ""}'], ""),
            # No thought key
            (['{"other": "value"}'], None),
        ],
    )
    def test_extract_thought_piece(self, args_parts: list, expected_final_thought):
        """Test thought extraction from think tool arguments."""
        state = ToolCallState("call-123", "think")

        result = None
        for part in args_parts:
            state.append_args(part)
            result = state.extract_thought_piece(part)

        if expected_final_thought is None:
            # All results should be None if no thought key
            assert result is None
        else:
            # Final state should have the complete thought stored
            assert state.prev_emitted_thought_chunk == expected_final_thought

    def test_extract_thought_piece_non_think_tool(self):
        """Test that non-think tools return None for thought extraction."""
        state = ToolCallState("call-123", "terminal")
        state.append_args('{"thought": "value"}')
        result = state.extract_thought_piece('{"thought": "value"}')
        assert result is None

    def test_repr(self):
        """Test string representation."""
        state = ToolCallState("call-123", "terminal")
        state.append_args('{"command": "ls"}')
        state.started = True
        repr_str = repr(state)
        assert "call-123" in repr_str
        assert "terminal" in repr_str
        assert "is_think=False" in repr_str
        assert "is_started=True" in repr_str
