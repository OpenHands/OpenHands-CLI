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

    def test_works_for_any_tool(self):
        """Same logic applies to all tools."""
        for tool_name in ["terminal", "file_editor", "think", "browser", "custom"]:
            state = ToolCallState("call-1", tool_name)
            state.append_args('{"key":"value"}')
            assert state.has_valid_skeleton is True, f"Failed for {tool_name}"

    def test_repr_includes_has_valid_skeleton(self):
        """Verify repr shows the has_valid_skeleton flag."""
        state = ToolCallState("call-1", "terminal")
        state.append_args('{"command":"ls"}')
        repr_str = repr(state)
        assert "has_valid_skeleton=True" in repr_str
