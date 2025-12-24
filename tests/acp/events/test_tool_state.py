"""Tests for ToolCallState (focus: extract_thought_piece with append_args streaming)."""

from __future__ import annotations

import pytest

from openhands_cli.acp_impl.events.tool_state import ToolCallState


class TestToolCallStateBasics:
    def test_init(self):
        state = ToolCallState("call-123", "terminal")
        assert state.tool_call_id == "call-123"
        assert state.tool_name == "terminal"
        assert state.is_think is False
        assert state.args == ""
        assert state.started is False

    def test_init_think(self):
        state = ToolCallState("call-456", "think")
        assert state.is_think is True

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
        """
        Monotonic growth contract:
          - thought grows: "" -> "hel" -> "hello" -> "hello world"
          - emit only the delta at each step: "hel", "lo", " world"
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
        assert out1 == "hel"
        assert state.prev_emitted_thought_chunk == "hel"

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
        assert state.extract_thought_piece() == "hello"
        assert state.prev_emitted_thought_chunk == "hello"

        # args can still "grow" by appending irrelevant tokens; thought stays same => no delta
        state.append_args("   ")
        assert state.extract_thought_piece() is None
        assert state.prev_emitted_thought_chunk == "hello"
