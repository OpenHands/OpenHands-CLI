"""Tests for ToolCallState (focus: extract_thought_piece with append_args streaming)."""

from __future__ import annotations

import pytest

from openhands_cli.acp_impl.events.shared_event_handler import THOUGHT_HEADER
from openhands_cli.acp_impl.events.tool_state import ToolCallState


class TestToolCallStateBasics:
    def test_init(self):
        state = ToolCallState("call-123", "terminal")
        assert state.tool_call_id == "call-123"
        assert state.tool_name == "terminal"
        assert state.is_think is False
        assert state.args == ""
        assert state.started is False
        assert state.thought_header_emitted is False

    def test_init_think(self):
        state = ToolCallState("call-456", "think")
        assert state.is_think is True
        assert state.thought_header_emitted is False

    def test_append_args_accumulates(self):
        state = ToolCallState("call-1", "terminal")
        state.append_args('{"comm')
        state.append_args('and":"ls"}')
        assert state.args == '{"command":"ls"}'


class TestExtractThoughtPiece:
    def test_non_think_tool_returns_none(self):
        state = ToolCallState("call-1", "terminal")
        state.append_args('{"thought":"hi"}')
        assert state.extract_thought_piece() is None

    def test_parse_error_returns_none_and_does_not_update_prev(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        state = ToolCallState("call-1", "think")
        state.append_args('{"thought":"hi"}')

        monkeypatch.setattr(state.lexer, "complete_json", lambda: "{not json")

        assert state.extract_thought_piece() is None
        assert state.prev_emitted_thought_chunk == ""

    def test_missing_thought_key_returns_none(self, monkeypatch: pytest.MonkeyPatch):
        state = ToolCallState("call-1", "think")
        state.append_args('{"other":"x"}')

        monkeypatch.setattr(state.lexer, "complete_json", lambda: '{"other":"x"}')

        assert state.extract_thought_piece() is None
        assert state.prev_emitted_thought_chunk == ""

    def test_empty_thought_returns_none(self, monkeypatch: pytest.MonkeyPatch):
        state = ToolCallState("call-1", "think")
        state.append_args('{"thought":""}')

        monkeypatch.setattr(state.lexer, "complete_json", lambda: '{"thought":""}')

        assert state.extract_thought_piece() is None
        assert state.prev_emitted_thought_chunk == ""

    def test_incremental_diff_emits_only_new_suffix(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Monotonic growth contract with header on first delta only.

        - thought grows: "" -> "hel" -> "hello" -> "hello world"
        - first delta includes THOUGHT_HEADER: "**Thought**:\nhel"
        - subsequent deltas are plain: "lo", " world"
        """
        state = ToolCallState("call-1", "think")

        # Deterministic snapshots from best-effort parse after each append.
        snapshots = iter(
            [
                '{"thought":"hel"}',
                '{"thought":"hello"}',
                '{"thought":"hello world"}',
            ]
        )
        monkeypatch.setattr(state.lexer, "complete_json", lambda: next(snapshots))

        state.append_args('{"thought":"hel')
        out1 = state.extract_thought_piece()
        assert out1 == THOUGHT_HEADER + "hel"
        assert state.prev_emitted_thought_chunk == "hel"
        assert state.thought_header_emitted is True

        state.append_args('lo"}')
        out2 = state.extract_thought_piece()
        assert out2 == "lo"
        assert state.prev_emitted_thought_chunk == "hello"

        state.append_args(' world"}')
        out3 = state.extract_thought_piece()
        assert out3 == " world"
        assert state.prev_emitted_thought_chunk == "hello world"

    def test_no_delta_when_thought_unchanged(self, monkeypatch: pytest.MonkeyPatch):
        state = ToolCallState("call-1", "think")

        snapshots = iter(
            [
                '{"thought":"hello"}',
                '{"thought":"hello"}',
            ]
        )
        monkeypatch.setattr(state.lexer, "complete_json", lambda: next(snapshots))

        state.append_args('{"thought":"hello"}')
        out = state.extract_thought_piece()
        assert out == THOUGHT_HEADER + "hello"
        assert state.prev_emitted_thought_chunk == "hello"

        # args can still "grow" by appending irrelevant tokens; thought
        # stays same => no delta
        state.append_args("   ")
        assert state.extract_thought_piece() is None
        assert state.prev_emitted_thought_chunk == "hello"


class TestHasValidSkeleton:
    """Tests for has_valid_skeleton property - prevents flickering tool calls."""

    def test_no_args_is_not_valid(self):
        """Empty args means no valid skeleton."""
        state = ToolCallState("call-1", "terminal")
        assert state.has_valid_skeleton is False

    def test_empty_dict_not_valid(self):
        """Empty dict has no keys with content."""
        state = ToolCallState("call-1", "terminal")
        state.append_args("{}")
        assert state.has_valid_skeleton is False

    def test_key_with_null_value_not_valid(self):
        """Key with null value doesn't count as content."""
        state = ToolCallState("call-1", "terminal")
        # Lexer completes '{"' to '{"":null}'
        state.append_args('{"')
        assert state.has_valid_skeleton is False

    def test_key_with_empty_string_not_valid(self):
        """Key with empty string doesn't count as content."""
        state = ToolCallState("call-1", "terminal")
        state.append_args('{"command":""}')
        assert state.has_valid_skeleton is False

    def test_key_with_non_empty_string_is_valid(self):
        """Key with any non-empty string content is valid."""
        state = ToolCallState("call-1", "terminal")
        state.append_args('{"command":"ls"}')
        assert state.has_valid_skeleton is True

    def test_key_with_number_is_valid(self):
        """Key with numeric value is valid."""
        state = ToolCallState("call-1", "some_tool")
        state.append_args('{"count":42}')
        assert state.has_valid_skeleton is True

    def test_key_with_boolean_is_valid(self):
        """Key with boolean value is valid."""
        state = ToolCallState("call-1", "some_tool")
        state.append_args('{"flag":true}')
        assert state.has_valid_skeleton is True

    def test_gradual_args_accumulation(self):
        """Simulate streaming: args build up gradually until valid."""
        state = ToolCallState("call-1", "terminal")

        # Just opening brace - empty dict
        state.append_args("{")
        assert state.has_valid_skeleton is False

        # Start a key - lexer completes to null value
        state = ToolCallState("call-2", "terminal")
        state.append_args('{"comm')
        assert state.has_valid_skeleton is False  # {"comm":null}

        # Empty string value
        state = ToolCallState("call-3", "terminal")
        state.append_args('{"command":"')
        assert state.has_valid_skeleton is False  # {"command":""}

        # Now with actual content
        state = ToolCallState("call-4", "terminal")
        state.append_args('{"command":"l')
        assert state.has_valid_skeleton is True  # {"command":"l"}

    def test_works_for_generic_tools(self):
        """Generic tools only need any key with content."""
        for tool_name in ["terminal", "think", "browser", "custom"]:
            state = ToolCallState("call-1", tool_name)
            state.append_args('{"key":"value"}')
            assert state.has_valid_skeleton is True, f"Failed for {tool_name}"

    def test_file_editor_requires_command_arg(self):
        """file_editor requires 'command' arg to determine kind (read vs edit)."""
        # Path only - not valid yet
        state = ToolCallState("call-1", "file_editor")
        state.append_args('{"path":"/test.py"}')
        assert state.has_valid_skeleton is False

        # With empty command - still not valid
        state = ToolCallState("call-2", "file_editor")
        state.append_args('{"path":"/test.py","command":""}')
        assert state.has_valid_skeleton is False

        # With command - now valid
        state = ToolCallState("call-3", "file_editor")
        state.append_args('{"path":"/test.py","command":"view"}')
        assert state.has_valid_skeleton is True

    def test_file_editor_command_streaming(self):
        """file_editor waits for command during streaming to avoid kind churn."""
        state = ToolCallState("call-1", "file_editor")

        # Chunk 1: path arrives first
        state.append_args('{"path":"/test.py"')
        assert state.has_valid_skeleton is False  # Still waiting for command

        # Chunk 2: command key starts but no value yet
        state.append_args(',"command":"')
        assert state.has_valid_skeleton is False  # Empty command

        # Chunk 3: command value arrives
        state.append_args('view"}')
        assert state.has_valid_skeleton is True  # Now we know it's a read

    def test_repr_includes_has_valid_skeleton(self):
        """Verify repr shows the has_valid_skeleton flag."""
        state = ToolCallState("call-1", "terminal")
        state.append_args('{"command":"ls"}')
        # Must check skeleton to trigger caching
        assert state.has_valid_skeleton
        repr_str = repr(state)
        assert "has_valid_skeleton=True" in repr_str

    def test_repr_shows_na_for_title_before_skeleton(self):
        """Verify repr shows N/A for title before skeleton is valid."""
        state = ToolCallState("call-1", "terminal")
        repr_str = repr(state)
        assert "title=N/A" in repr_str
        assert "has_valid_skeleton=False" in repr_str


class TestKind:
    """Tests for the kind property on ToolCallState."""

    def test_kind_raises_before_valid_skeleton(self):
        """Accessing kind before valid skeleton raises ValueError."""
        state = ToolCallState("call-1", "terminal")
        with pytest.raises(ValueError, match="Cannot access kind"):
            _ = state.kind

    @pytest.mark.parametrize(
        "tool_name,args,expected",
        [
            ("think", '{"thought":"x"}', "think"),
            ("browser", '{"url":"x"}', "fetch"),
            ("browser_use", '{"action":"x"}', "fetch"),
            ("browser_navigate", '{"url":"x"}', "fetch"),
            ("terminal", '{"command":"ls"}', "execute"),
            ("unknown_tool", '{"key":"x"}', "other"),
        ],
    )
    def test_kind_by_tool_name(self, tool_name: str, args: str, expected: str):
        """Kind is determined by tool name for most tools."""
        state = ToolCallState("call-1", tool_name)
        state.append_args(args)
        assert state.has_valid_skeleton
        assert state.kind == expected

    @pytest.mark.parametrize(
        "partial_json,expected",
        [
            ('{"command":"view","path":"/test.py"}', "read"),
            ('{"command":"v","path":"/test.py"}', "read"),  # prefix of view
            ('{"command":"vi","path":"/test.py"}', "read"),  # prefix of view
            ('{"command":"vie","path":"/test.py"}', "read"),  # prefix of view
            ('{"command":"str_replace","path":"/test.py"}', "edit"),
            ('{"command":"create","path":"/test.py"}', "edit"),
            ('{"command":"s","path":"/test.py"}', "edit"),  # not a prefix of view
        ],
    )
    def test_file_editor_kind_from_streaming_args(
        self, partial_json: str, expected: str
    ):
        """file_editor kind depends on command arg, with prefix matching for 'view'."""
        state = ToolCallState("call-1", "file_editor")
        state.append_args(partial_json)
        assert state.has_valid_skeleton
        assert state.kind == expected

    def test_kind_is_cached(self):
        """Kind is cached after first access."""
        state = ToolCallState("call-1", "terminal")
        state.append_args('{"command":"ls"}')
        assert state.has_valid_skeleton
        _ = state.kind
        assert state._cached_kind == "execute"


class TestTitle:
    """Tests for the title property on ToolCallState."""

    def test_title_raises_before_valid_skeleton(self):
        """Accessing title before valid skeleton raises ValueError."""
        state = ToolCallState("call-1", "terminal")
        with pytest.raises(ValueError, match="Cannot access title"):
            _ = state.title

    def test_task_tracker_title_constant(self):
        state = ToolCallState("call-1", "task_tracker")
        state.append_args('{"command":"plan"}')
        assert state.has_valid_skeleton
        assert state.title == "Plan updated"

    @pytest.mark.parametrize(
        "tool_name,partial_json,expected",
        [
            ("file_editor", '{"command":"view","path":"/test.py"}', "Reading /test.py"),
            ("file_editor", '{"command":"v","path":"/test.py"}', "Reading /test.py"),
            (
                "file_editor",
                '{"command":"str_replace","path":"/test.py"}',
                "Editing /test.py",
            ),
            ("terminal", '{"command":"ls -la"}', "ls -la"),
            # file_editor missing path falls through to tool_name
            ("file_editor", '{"command":"view"}', "file_editor"),
            ("file_editor", '{"command":"view","path":""}', "file_editor"),
        ],
    )
    def test_title_from_streaming_args(
        self, tool_name: str, partial_json: str, expected: str
    ):
        """Title is computed from partial args during streaming."""
        state = ToolCallState("call-1", tool_name)
        state.append_args(partial_json)
        assert state.has_valid_skeleton
        assert state.title == expected

    def test_title_updates_as_args_arrive(self):
        """Title updates as more args stream in (not cached)."""
        state = ToolCallState("call-1", "file_editor")
        state.append_args('{"command":"view"')
        assert state.has_valid_skeleton
        assert state.title == "file_editor"  # No path yet

        state.append_args(',"path":"/test.py"}')
        assert state.title == "Reading /test.py"  # Path arrived
