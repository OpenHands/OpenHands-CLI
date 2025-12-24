"""Tests for TokenBasedEventSubscriber token streaming (minimal, high-impact)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acp.schema import (
    AgentMessageChunk,
    AgentThoughtChunk,
    ToolCallProgress,
    ToolCallStart,
)

from openhands.sdk import TextContent
from openhands.sdk.event import ActionEvent, ObservationEvent
from openhands.sdk.llm import MessageToolCall
from openhands.tools.terminal import TerminalAction, TerminalObservation
from openhands_cli.acp_impl.events.token_streamer import TokenBasedEventSubscriber
from openhands_cli.acp_impl.events.tool_state import ToolCallState


@pytest.fixture
def mock_connection():
    return AsyncMock()


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def token_subscriber(mock_connection, event_loop):
    return TokenBasedEventSubscriber(
        session_id="test-session",
        conn=mock_connection,
        loop=event_loop,
    )


def _chunk(*, content=None, reasoning=None, tool_calls=None):
    """Build a minimal LLMStreamChunk-like object."""
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = content
    delta.reasoning_content = reasoning
    delta.tool_calls = tool_calls
    choice = MagicMock()
    choice.delta = delta
    chunk.choices = [choice]
    return chunk


def _tool_call(*, index=0, tool_call_id=None, name=None, arguments=None):
    """Build a minimal tool_call-like object."""
    tc = MagicMock()
    tc.index = index
    tc.id = tool_call_id
    fn = MagicMock()
    fn.name = name
    fn.arguments = arguments
    tc.function = fn
    return tc


class TestInit:
    def test_initialization(self, mock_connection, event_loop):
        subscriber = TokenBasedEventSubscriber(
            session_id="session-123",
            conn=mock_connection,
            loop=event_loop,
        )
        assert subscriber.session_id == "session-123"
        assert subscriber.conn is mock_connection
        assert subscriber.loop is event_loop
        assert subscriber.conversation is None
        assert subscriber._streaming_tool_calls == {}


class TestOnTokenContentAndReasoning:
    def test_content_emits_message_chunk(
        self, token_subscriber, mock_connection, event_loop
    ):
        chunk = _chunk(content="Hello", reasoning=None, tool_calls=None)

        with patch.object(event_loop, "is_running", return_value=False):
            token_subscriber.on_token(chunk)

        assert mock_connection.session_update.called
        update = mock_connection.session_update.call_args[1]["update"]
        assert isinstance(update, AgentMessageChunk)
        assert update.session_update == "agent_message_chunk"

    def test_reasoning_emits_thought_chunk(
        self, token_subscriber, mock_connection, event_loop
    ):
        chunk = _chunk(content=None, reasoning="Thinking...", tool_calls=None)

        with patch.object(event_loop, "is_running", return_value=False):
            token_subscriber.on_token(chunk)

        assert mock_connection.session_update.called
        update = mock_connection.session_update.call_args[1]["update"]
        assert isinstance(update, AgentThoughtChunk)
        assert update.session_update == "agent_thought_chunk"

    def test_empty_strings_do_not_emit(
        self, token_subscriber, mock_connection, event_loop
    ):
        chunk = _chunk(content="", reasoning="", tool_calls=None)

        with patch.object(event_loop, "is_running", return_value=False):
            token_subscriber.on_token(chunk)

        assert not mock_connection.session_update.called

    def test_choice_without_delta_is_ignored(
        self, token_subscriber, mock_connection, event_loop
    ):
        chunk = MagicMock()
        choice = MagicMock()
        choice.delta = None
        chunk.choices = [choice]

        with patch.object(event_loop, "is_running", return_value=False):
            token_subscriber.on_token(chunk)

        assert not mock_connection.session_update.called


class TestToolCallStreaming:
    def test_non_think_tool_call_emits_start_then_progress(
        self, token_subscriber, mock_connection, event_loop
    ):
        """
        First chunk for a non-think tool call should:
          - create ToolCallState
          - emit ToolCallStart once (started=True)
          - append args, then emit ToolCallProgress update
        """
        tc = _tool_call(
            index=0,
            tool_call_id="call-123",
            name="terminal",
            arguments='{"command":"ls"}',
        )
        chunk = _chunk(tool_calls=[tc])

        with patch.object(event_loop, "is_running", return_value=False):
            token_subscriber.on_token(chunk)

        # state tracked
        state = token_subscriber._streaming_tool_calls[0]
        assert state.tool_call_id == "call-123"
        assert state.tool_name == "terminal"
        assert state.started is True

        # start + progress emitted (order matters)
        assert mock_connection.session_update.call_count == 2
        update1 = mock_connection.session_update.call_args_list[0].kwargs["update"]
        update2 = mock_connection.session_update.call_args_list[1].kwargs["update"]

        assert isinstance(update1, ToolCallStart)
        assert isinstance(update2, ToolCallProgress)
        assert update1.session_update == "tool_call"
        assert update2.session_update == "tool_call_update"

    def test_subsequent_tool_call_chunk_accumulates_args_and_updates_progress(
        self, token_subscriber, mock_connection, event_loop
    ):
        # chunk1 starts tool call + partial args
        tc1 = _tool_call(
            index=0,
            tool_call_id="call-123",
            name="terminal",
            arguments='{"comm',
        )
        # chunk2 continues args (id/name omitted in later streaming chunks)
        tc2 = _tool_call(
            index=0,
            tool_call_id=None,
            name=None,
            arguments='and":"ls"}',
        )

        with patch.object(event_loop, "is_running", return_value=False):
            token_subscriber.on_token(_chunk(tool_calls=[tc1]))
            token_subscriber.on_token(_chunk(tool_calls=[tc2]))

        state = token_subscriber._streaming_tool_calls[0]
        assert state.args == '{"command":"ls"}'

        # Expect:
        # - chunk1 emits start + progress
        # - chunk2 emits progress
        # => total 3 updates
        assert mock_connection.session_update.call_count == 3
        assert (
            mock_connection.session_update.call_args_list[-1]
            .kwargs["update"]
            .session_update
            == "tool_call_update"
        )

    def test_think_tool_does_not_start_tool_call_and_emits_thought_when_available(
        self, token_subscriber, mock_connection, event_loop
    ):
        """
        Think tool:
          - state is tracked but started stays False
          - if extract_thought_piece() yields text, emit agent_thought_chunk
        """
        tc = _tool_call(
            index=0,
            tool_call_id="call-think-1",
            name="think",
            arguments='{"thought":"hi"}',
        )
        chunk = _chunk(tool_calls=[tc])

        with patch.object(ToolCallState, "extract_thought_piece", return_value="hi"):
            with patch.object(event_loop, "is_running", return_value=False):
                token_subscriber.on_token(chunk)

        state = token_subscriber._streaming_tool_calls[0]
        assert state.is_think is True
        assert state.started is False

        # should emit thought update (and NOT tool_call_start)
        assert mock_connection.session_update.called
        updates = [
            c.kwargs["update"].session_update
            for c in mock_connection.session_update.call_args_list
        ]
        assert "agent_thought_chunk" in updates
        assert "tool_call_start" not in updates

    def test_tool_call_state_replaced_when_new_id_at_same_index(
        self, token_subscriber, mock_connection, event_loop
    ):
        """
        If a new tool_call_id arrives at the same index, state should be replaced.
        """
        tc1 = _tool_call(
            index=0, tool_call_id="call-1", name="terminal", arguments='{"command":"a"}'
        )
        tc2 = _tool_call(
            index=0, tool_call_id="call-2", name="terminal", arguments='{"command":"b"}'
        )

        with patch.object(event_loop, "is_running", return_value=False):
            token_subscriber.on_token(_chunk(tool_calls=[tc1]))
            first_state = token_subscriber._streaming_tool_calls[0]
            token_subscriber.on_token(_chunk(tool_calls=[tc2]))
            second_state = token_subscriber._streaming_tool_calls[0]

        assert first_state.tool_call_id == "call-1"
        assert second_state.tool_call_id == "call-2"
        assert first_state is not second_state


class TestErrorHandling:
    def test_on_token_logs_and_continues_on_error(self, token_subscriber, caplog):
        """Token callbacks should be best-effort and non-throwing.

        Errors are logged but don't raise, so one malformed chunk won't
        kill the stream.
        """
        chunk = _chunk(content=None, reasoning=None, tool_calls=[MagicMock()])

        with patch.object(
            token_subscriber,
            "_handle_tool_call_streaming",
            side_effect=RuntimeError("boom"),
        ):
            # Should NOT raise - errors are caught and logged
            token_subscriber.on_token(chunk)

        # Verify error was logged
        assert any("boom" in record.message for record in caplog.records)
        assert any(record.levelname == "WARNING" for record in caplog.records)


class TestScheduleUpdate:
    def test_schedule_update_loop_running_uses_run_coroutine_threadsafe(
        self, mock_connection
    ):
        loop = asyncio.new_event_loop()
        subscriber = TokenBasedEventSubscriber(
            session_id="test-session",
            conn=mock_connection,
            loop=loop,
        )

        from acp import update_agent_message_text

        update = update_agent_message_text("test")

        with patch.object(loop, "is_running", return_value=True):
            with patch("asyncio.run_coroutine_threadsafe") as mock_rcts:
                subscriber._schedule_update(update)
                mock_rcts.assert_called_once()

        loop.close()


@pytest.mark.asyncio
async def test_terminal_tool_lifecycle_stream_then_action_then_observation():
    """
    Lifecycle:
      1) on_token streams partial TerminalAction -> emits
         ToolCallStart(in_progress) then ToolCallProgress(in_progress)
      2) unstreamed ActionEvent arrives (same tool_call_id) -> may emit
         another ToolCallStart(in_progress)
      3) unstreamed ObservationEvent arrives (same tool_call_id) -> emits
         ToolCallProgress(completed)

    We assert that, for the same tool_call_id, the observed ACP updates
    progress:
      tool_call (in_progress) -> tool_call_update (in_progress) ->
      tool_call_update (completed)
    """
    conn = AsyncMock()
    loop = asyncio.get_running_loop()
    subscriber = TokenBasedEventSubscriber(
        session_id="test-session",
        conn=conn,
        loop=loop,
    )

    tool_call_id = "call-123"
    action_id = "action-123"

    # -----------------------
    # 1) Stream tokens
    # -----------------------
    tc1 = _tool_call(
        index=0,
        tool_call_id=tool_call_id,
        name="terminal",
        arguments='{"comm',
    )
    tc2 = _tool_call(
        index=0,
        tool_call_id=None,  # later chunks often omit id/name
        name=None,
        arguments='and":"ls"}',
    )

    # with patch.object(loop, "is_running", return_value=False):
    subscriber.on_token(_chunk(tool_calls=[tc1]))
    subscriber.on_token(_chunk(tool_calls=[tc2]))

    # -----------------------
    # 2) Final ActionEvent arrives (same tool_call_id)
    # -----------------------
    action = TerminalAction(command="ls")
    message_tool_call = MessageToolCall(
        id=tool_call_id,
        name="terminal",
        arguments='{"command":"ls"}',
        origin="completion",
    )

    # NOTE: depending on your ActionEvent schema, you may need additional
    # required fields. These are common in OpenHands events; adjust if your
    # constructor differs.
    action_event = ActionEvent(
        id="evt-action-1",
        timestamp=datetime.now(UTC).isoformat(),
        tool_call_id=tool_call_id,
        tool_name="terminal",
        action=action,
        thought=[],
        llm_response_id="llm-1",
        tool_call=message_tool_call,
    )
    await subscriber.unstreamed_event_handler(action_event)

    # -----------------------
    # 3) ObservationEvent arrives (same tool_call_id)
    # -----------------------
    # Create a successful observation (adjust required fields if your model differs).
    obs = TerminalObservation(
        command="ls",
        exit_code=0,
        timeout=False,
        content=[TextContent(text="file1\nfile2\n")],
    )
    obs_event = ObservationEvent(
        tool_name="terminal",
        tool_call_id=tool_call_id,
        observation=obs,
        action_id=action_id,  # REQUIRED linkage
    )

    await subscriber.unstreamed_event_handler(obs_event)

    await subscriber.unstreamed_event_handler(obs_event)

    # -----------------------
    # Assert: status progression
    # -----------------------
    # Gather ONLY the updates related to our tool_call_id.
    updates = []
    for call in conn.session_update.call_args_list:
        update = call.kwargs["update"]
        # Filter only tool-call updates for this tool_call_id
        if getattr(update, "tool_call_id", None) == tool_call_id:
            updates.append(update)

    assert updates, "Expected at least one ACP update for tool_call_id"

    # We want to see:
    # - at least one ToolCallStart with status in_progress
    # - at least one ToolCallProgress with status in_progress
    # - final ToolCallProgress with status completed
    starts = [u for u in updates if isinstance(u, ToolCallStart)]
    progresses = [u for u in updates if isinstance(u, ToolCallProgress)]

    assert any(isinstance(s, ToolCallStart) for s in starts), (
        "Expected a ToolCallStart from streaming and/or ActionEvent"
    )
    assert any(isinstance(p, ToolCallProgress) for p in progresses), (
        "Expected at least one ToolCallProgress during streaming"
    )

    # The last tool-call-related update should be completion.
    last = updates[-1]
    assert isinstance(last, ToolCallProgress), (
        "Expected final update to be ToolCallProgress"
    )
    assert last.status == "completed"
