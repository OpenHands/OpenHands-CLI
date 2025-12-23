"""Tests for TokenBasedEventSubscriber and token streaming functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acp.schema import SessionUpdate3, SessionUpdate4

from openhands_cli.acp_impl.events.token_streamer import TokenBasedEventSubscriber


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def event_loop():
    """Create an event loop for tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def token_subscriber(mock_connection, event_loop):
    """Create a TokenBasedEventSubscriber instance."""
    return TokenBasedEventSubscriber(
        session_id="test-session",
        conn=mock_connection,
        loop=event_loop,
    )


class TestTokenBasedEventSubscriberInit:
    """Tests for TokenBasedEventSubscriber initialization."""

    def test_initialization(self, mock_connection, event_loop):
        """Test basic initialization of TokenBasedEventSubscriber."""
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


class TestOnTokenContent:
    """Tests for on_token handling of content/reasoning."""

    def test_on_token_with_content(self, token_subscriber, mock_connection, event_loop):
        """Test that content tokens trigger agent message updates."""
        # Create a mock streaming chunk with content
        chunk = MagicMock()
        delta = MagicMock()
        delta.content = "Hello, "
        delta.reasoning_content = None
        delta.tool_calls = None
        choice = MagicMock()
        choice.delta = delta
        chunk.choices = [choice]

        # Process the token synchronously (using loop.run_until_complete)
        with patch.object(event_loop, 'is_running', return_value=False):
            token_subscriber.on_token(chunk)

        # Verify that session_update was called for content
        assert mock_connection.session_update.called

    def test_on_token_with_reasoning(self, token_subscriber, mock_connection, event_loop):
        """Test that reasoning tokens trigger thought updates."""
        chunk = MagicMock()
        delta = MagicMock()
        delta.content = None
        delta.reasoning_content = "Let me think..."
        delta.tool_calls = None
        choice = MagicMock()
        choice.delta = delta
        chunk.choices = [choice]

        with patch.object(event_loop, 'is_running', return_value=False):
            token_subscriber.on_token(chunk)

        # Verify that session_update was called for reasoning
        assert mock_connection.session_update.called
        call_kwargs = mock_connection.session_update.call_args[1]
        update = call_kwargs["update"]
        # AgentThoughtChunk is SessionUpdate3
        assert isinstance(update, SessionUpdate3)
        assert update.session_update == "agent_thought_chunk"

    def test_on_token_empty_content(self, token_subscriber, mock_connection, event_loop):
        """Test that empty content doesn't trigger updates."""
        chunk = MagicMock()
        delta = MagicMock()
        delta.content = ""
        delta.reasoning_content = ""
        delta.tool_calls = None
        choice = MagicMock()
        choice.delta = delta
        chunk.choices = [choice]

        with patch.object(event_loop, 'is_running', return_value=False):
            token_subscriber.on_token(chunk)

        # Verify that session_update was NOT called for empty content
        assert not mock_connection.session_update.called

    def test_on_token_no_delta(self, token_subscriber, mock_connection, event_loop):
        """Test that chunks without delta are handled gracefully."""
        chunk = MagicMock()
        choice = MagicMock()
        choice.delta = None
        chunk.choices = [choice]

        with patch.object(event_loop, 'is_running', return_value=False):
            token_subscriber.on_token(chunk)

        # Should not crash and should not call session_update
        assert not mock_connection.session_update.called


class TestOnTokenToolCalls:
    """Tests for on_token handling of tool calls."""

    def test_on_token_tool_call_start(self, token_subscriber, mock_connection, event_loop):
        """Test that tool call start triggers tool_call notification."""
        chunk = MagicMock()
        delta = MagicMock()
        delta.content = None
        delta.reasoning_content = None

        # Create tool call
        tool_call = MagicMock()
        tool_call.index = 0
        tool_call.id = "call-123"
        function = MagicMock()
        function.name = "terminal"
        function.arguments = '{"command": "ls"}'
        tool_call.function = function
        delta.tool_calls = [tool_call]

        choice = MagicMock()
        choice.delta = delta
        chunk.choices = [choice]

        with patch.object(event_loop, 'is_running', return_value=False):
            token_subscriber.on_token(chunk)

        # Verify tool call state was created
        assert 0 in token_subscriber._streaming_tool_calls
        state = token_subscriber._streaming_tool_calls[0]
        assert state.tool_call_id == "call-123"
        assert state.tool_name == "terminal"
        assert state.started is True

    def test_on_token_think_tool_not_started(self, token_subscriber, mock_connection, event_loop):
        """Test that think tool calls are not started (streamed as thoughts)."""
        chunk = MagicMock()
        delta = MagicMock()
        delta.content = None
        delta.reasoning_content = None

        # Create think tool call
        tool_call = MagicMock()
        tool_call.index = 0
        tool_call.id = "call-think-123"
        function = MagicMock()
        function.name = "think"
        function.arguments = '{"thought": "Thinking..."}'
        tool_call.function = function
        delta.tool_calls = [tool_call]

        choice = MagicMock()
        choice.delta = delta
        chunk.choices = [choice]

        with patch.object(event_loop, 'is_running', return_value=False):
            token_subscriber.on_token(chunk)

        # Think tool should be tracked but NOT started
        assert 0 in token_subscriber._streaming_tool_calls
        state = token_subscriber._streaming_tool_calls[0]
        assert state.is_think is True
        assert state.started is False

    def test_on_token_tool_call_streaming_args(self, token_subscriber, mock_connection, event_loop):
        """Test that streaming arguments are accumulated."""
        # First chunk - start tool call
        chunk1 = MagicMock()
        delta1 = MagicMock()
        delta1.content = None
        delta1.reasoning_content = None
        tool_call1 = MagicMock()
        tool_call1.index = 0
        tool_call1.id = "call-123"
        function1 = MagicMock()
        function1.name = "terminal"
        function1.arguments = '{"comm'
        tool_call1.function = function1
        delta1.tool_calls = [tool_call1]
        choice1 = MagicMock()
        choice1.delta = delta1
        chunk1.choices = [choice1]

        # Second chunk - continue args
        chunk2 = MagicMock()
        delta2 = MagicMock()
        delta2.content = None
        delta2.reasoning_content = None
        tool_call2 = MagicMock()
        tool_call2.index = 0
        tool_call2.id = None  # ID only sent on first chunk
        function2 = MagicMock()
        function2.name = None  # Name only sent on first chunk
        function2.arguments = 'and": "ls"}'
        tool_call2.function = function2
        delta2.tool_calls = [tool_call2]
        choice2 = MagicMock()
        choice2.delta = delta2
        chunk2.choices = [choice2]

        with patch.object(event_loop, 'is_running', return_value=False):
            token_subscriber.on_token(chunk1)
            token_subscriber.on_token(chunk2)

        # Verify args were accumulated
        state = token_subscriber._streaming_tool_calls[0]
        assert state.args == '{"command": "ls"}'

    def test_on_token_multiple_tool_calls(self, token_subscriber, mock_connection, event_loop):
        """Test handling multiple tool calls in same stream."""
        # First tool call
        chunk1 = MagicMock()
        delta1 = MagicMock()
        delta1.content = None
        delta1.reasoning_content = None
        tool_call1 = MagicMock()
        tool_call1.index = 0
        tool_call1.id = "call-1"
        function1 = MagicMock()
        function1.name = "terminal"
        function1.arguments = '{"command": "ls"}'
        tool_call1.function = function1
        delta1.tool_calls = [tool_call1]
        choice1 = MagicMock()
        choice1.delta = delta1
        chunk1.choices = [choice1]

        # Second tool call (different index)
        chunk2 = MagicMock()
        delta2 = MagicMock()
        delta2.content = None
        delta2.reasoning_content = None
        tool_call2 = MagicMock()
        tool_call2.index = 1
        tool_call2.id = "call-2"
        function2 = MagicMock()
        function2.name = "file_editor"
        function2.arguments = '{"path": "/test.py"}'
        tool_call2.function = function2
        delta2.tool_calls = [tool_call2]
        choice2 = MagicMock()
        choice2.delta = delta2
        chunk2.choices = [choice2]

        with patch.object(event_loop, 'is_running', return_value=False):
            token_subscriber.on_token(chunk1)
            token_subscriber.on_token(chunk2)

        # Both tool calls should be tracked
        assert 0 in token_subscriber._streaming_tool_calls
        assert 1 in token_subscriber._streaming_tool_calls
        assert token_subscriber._streaming_tool_calls[0].tool_name == "terminal"
        assert token_subscriber._streaming_tool_calls[1].tool_name == "file_editor"


class TestUnstreamedEventHandler:
    """Tests for unstreamed_event_handler method."""

    @pytest.mark.asyncio
    async def test_skip_conversation_state_update(self, token_subscriber, mock_connection):
        """Test that ConversationStateUpdateEvent is skipped."""
        from openhands.sdk.event import ConversationStateUpdateEvent

        event = ConversationStateUpdateEvent(source="environment", key="test", value="test")
        await token_subscriber.unstreamed_event_handler(event)

        # Should not call session_update
        assert not mock_connection.session_update.called

    @pytest.mark.asyncio
    async def test_handle_pause_event(self, token_subscriber, mock_connection):
        """Test handling of PauseEvent."""
        from openhands.sdk.event import PauseEvent

        event = PauseEvent(source="agent")
        await token_subscriber.unstreamed_event_handler(event)

        # Should call session_update with thought
        assert mock_connection.session_update.called
        call_kwargs = mock_connection.session_update.call_args[1]
        update = call_kwargs["update"]
        assert isinstance(update, SessionUpdate3)
        assert update.session_update == "agent_thought_chunk"

    @pytest.mark.asyncio
    async def test_handle_system_prompt_event(self, token_subscriber, mock_connection):
        """Test handling of SystemPromptEvent."""
        from openhands.sdk import TextContent
        from openhands.sdk.event import SystemPromptEvent

        event = SystemPromptEvent(
            source="agent",
            system_prompt=TextContent(text="System prompt"),
            tools=[],
        )
        await token_subscriber.unstreamed_event_handler(event)

        assert mock_connection.session_update.called
        call_kwargs = mock_connection.session_update.call_args[1]
        update = call_kwargs["update"]
        assert isinstance(update, SessionUpdate3)


class TestScheduleUpdate:
    """Tests for _schedule_update method."""

    def test_schedule_update_loop_not_running(self, token_subscriber, mock_connection, event_loop):
        """Test scheduling update when loop is not running."""
        from acp import update_agent_message_text

        update = update_agent_message_text("test")

        with patch.object(event_loop, 'is_running', return_value=False):
            token_subscriber._schedule_update(update)

        assert mock_connection.session_update.called

    def test_schedule_update_loop_running(self, mock_connection):
        """Test scheduling update when loop is already running."""
        loop = asyncio.new_event_loop()
        subscriber = TokenBasedEventSubscriber(
            session_id="test-session",
            conn=mock_connection,
            loop=loop,
        )

        from acp import update_agent_message_text

        update = update_agent_message_text("test")

        # Simulate loop running by using run_coroutine_threadsafe
        with patch.object(loop, 'is_running', return_value=True):
            with patch('asyncio.run_coroutine_threadsafe') as mock_rcts:
                subscriber._schedule_update(update)
                mock_rcts.assert_called_once()

        loop.close()
