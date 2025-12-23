"""Tests for LLM streaming functionality in ACP implementation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from acp.schema import AgentMessageChunk, AgentThoughtChunk, TextContentBlock
from litellm.types.utils import ModelResponseStream

from openhands_cli.acp_impl.agent import OpenHandsACPAgent
from openhands_cli.acp_impl.event import EventSubscriber


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def acp_agent(mock_connection):
    """Create an OpenHands ACP agent instance."""
    return OpenHandsACPAgent(mock_connection, "always-ask")


@pytest.fixture
def event_subscriber(mock_connection):
    """Create an EventSubscriber instance."""
    loop = asyncio.new_event_loop()
    return EventSubscriber("test-session", mock_connection, loop=loop)


@pytest.fixture
def mock_streaming_chunk():
    """Create a mock streaming chunk."""
    chunk = MagicMock(spec=ModelResponseStream)
    choice = MagicMock()
    delta = MagicMock()
    choice.delta = delta
    chunk.choices = [choice]
    return chunk, delta


@pytest.fixture
def mock_tool_call():
    """Create a mock tool call for streaming."""
    tool_call = MagicMock()
    tool_call.index = 0
    function = MagicMock()
    tool_call.function = function
    return tool_call, function


@pytest.mark.asyncio
async def test_token_callback_creation(event_subscriber):
    """Test that on_token method is callable."""
    assert callable(event_subscriber.on_token)


@pytest.mark.asyncio
async def test_streaming_regular_content(
    event_subscriber, mock_connection, mock_streaming_chunk
):
    """Test streaming regular content tokens."""
    chunk, delta = mock_streaming_chunk

    # Set up delta with regular content
    delta.content = "Hello world"
    delta.reasoning_content = None
    delta.tool_calls = None

    # Test the streaming logic by calling _send_streaming_chunk directly
    await event_subscriber._send_streaming_chunk("Hello world", is_reasoning=False)

    # Verify session_update was called with AgentMessageChunk
    mock_connection.session_update.assert_called()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == "test-session"
    update = call_args[1]["update"]
    assert isinstance(update, AgentMessageChunk)
    assert update.session_update == "agent_message_chunk"
    assert isinstance(update.content, TextContentBlock)
    assert update.content.text == "Hello world"


@pytest.mark.asyncio
async def test_streaming_reasoning_content(
    event_subscriber, mock_connection, mock_streaming_chunk
):
    """Test streaming reasoning content tokens."""
    chunk, delta = mock_streaming_chunk

    # Set up delta with reasoning content
    delta.content = None
    delta.reasoning_content = "I need to think about this..."
    delta.tool_calls = None

    # Test the streaming logic by calling _send_streaming_chunk directly
    await event_subscriber._send_streaming_chunk(
        "I need to think about this...", is_reasoning=True
    )

    # Verify session_update was called with AgentThoughtChunk
    mock_connection.session_update.assert_called()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == "test-session"
    update = call_args[1]["update"]
    assert isinstance(update, AgentThoughtChunk)
    assert update.session_update == "agent_thought_chunk"
    assert update.content.text == "I need to think about this..."


@pytest.mark.asyncio
async def test_streaming_error_handling(event_subscriber, mock_connection):
    """Test that streaming errors are handled gracefully."""
    # Create a malformed chunk that will cause an error
    bad_chunk = MagicMock()
    bad_chunk.choices = None  # This should cause an error

    # Process the bad chunk - should raise RequestError due to our implementation
    with pytest.raises(Exception):  # Should raise RequestError.internal_error
        event_subscriber.on_token(bad_chunk)


@pytest.mark.asyncio
async def test_conversation_setup_enables_streaming(acp_agent):
    """Test that conversation setup enables streaming on the LLM."""
    session_id = str(uuid4())

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load_specs,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conversation_class,
        patch(
            "openhands_cli.acp_impl.agent.EventSubscriber"
        ) as mock_event_subscriber_class,
    ):
        # Mock agent with LLM
        mock_agent = MagicMock()
        mock_llm = MagicMock()
        mock_agent.llm = mock_llm
        mock_load_specs.return_value = mock_agent

        # Mock LLM model_copy to return updated LLM with streaming enabled
        mock_updated_llm = MagicMock()
        mock_llm.model_copy.return_value = mock_updated_llm

        # Mock agent model_copy to return updated agent
        mock_updated_agent = MagicMock()
        mock_updated_agent.llm = mock_updated_llm
        mock_agent.model_copy.return_value = mock_updated_agent

        # Mock EventSubscriber instance
        mock_subscriber = MagicMock()
        mock_subscriber.on_token = MagicMock()
        mock_event_subscriber_class.return_value = mock_subscriber

        # Call the method
        acp_agent._setup_acp_conversation(session_id)

        # Verify that streaming was enabled on the LLM
        mock_llm.model_copy.assert_called_once_with(update={"stream": True})

        # Verify that agent was updated with streaming-enabled LLM
        mock_agent.model_copy.assert_called_once_with(update={"llm": mock_updated_llm})

        # Verify that EventSubscriber was created with loop parameter
        mock_event_subscriber_class.assert_called_once()
        call_args = mock_event_subscriber_class.call_args
        assert call_args[0][0] == session_id  # session_id
        assert call_args[0][1] == acp_agent._conn  # conn
        assert "loop" in call_args[1]  # loop kwarg

        # Verify that Conversation was created with token_callbacks
        mock_conversation_class.assert_called_once()
        call_kwargs = mock_conversation_class.call_args[1]
        assert "token_callbacks" in call_kwargs
        assert len(call_kwargs["token_callbacks"]) == 1
        assert call_kwargs["token_callbacks"][0] == mock_subscriber.on_token


@pytest.mark.asyncio
async def test_send_streaming_chunk_regular_content(event_subscriber, mock_connection):
    """Test sending regular streaming chunk."""
    content = "Hello world"

    await event_subscriber._send_streaming_chunk(content, is_reasoning=False)

    # Verify session_update was called correctly
    mock_connection.session_update.assert_called_once()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == "test-session"
    update = call_args[1]["update"]
    assert isinstance(update, AgentMessageChunk)
    assert update.content.text == "Hello world"


@pytest.mark.asyncio
async def test_send_streaming_chunk_reasoning_content(
    event_subscriber, mock_connection
):
    """Test sending reasoning streaming chunk."""
    content = "I need to analyze this"

    await event_subscriber._send_streaming_chunk(content, is_reasoning=True)

    # Verify session_update was called correctly
    mock_connection.session_update.assert_called_once()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == "test-session"
    update = call_args[1]["update"]
    assert isinstance(update, AgentThoughtChunk)
    assert update.content.text == "I need to analyze this"


@pytest.mark.asyncio
async def test_send_streaming_chunk_error_handling(event_subscriber, mock_connection):
    """Test that streaming chunk sending handles errors gracefully."""
    content = "test content"

    # Make session_update raise an exception
    mock_connection.session_update.side_effect = Exception("Connection error")

    # Should not raise an exception
    try:
        await event_subscriber._send_streaming_chunk(content)
    except Exception as e:
        pytest.fail(
            f"_send_streaming_chunk should handle errors gracefully, but raised: {e}"
        )


@pytest.mark.asyncio
async def test_think_tool_detection(event_subscriber, mock_tool_call):
    """Test that think tool is properly detected during streaming."""
    tool_call, function = mock_tool_call
    tool_call.id = "tool_123"
    function.name = "think"
    function.arguments = None

    # Initially, no tool calls should be tracked
    assert 0 not in event_subscriber._streaming_tool_calls

    # Handle the tool call with think name
    event_subscriber._handle_tool_call_streaming(tool_call)

    # Now the index should be tracked with is_think=True
    assert 0 in event_subscriber._streaming_tool_calls
    assert event_subscriber._streaming_tool_calls[0]["is_think"] is True
    assert event_subscriber._streaming_tool_calls[0]["name"] == "think"


@pytest.mark.asyncio
async def test_think_tool_arguments_streaming(
    event_subscriber, mock_connection, mock_tool_call
):
    """Test that think tool arguments are streamed as AgentThoughtChunk."""
    tool_call, function = mock_tool_call
    tool_call.id = "tool_123"

    # First call: register the think tool
    function.name = "think"
    function.arguments = ""
    event_subscriber._handle_tool_call_streaming(tool_call)

    # Second call: stream the thought argument
    function.name = None  # Name is None in subsequent chunks
    function.arguments = "This is my thought"

    await event_subscriber._send_streaming_chunk(
        "This is my thought", is_reasoning=True
    )

    # Verify session_update was called with AgentThoughtChunk
    mock_connection.session_update.assert_called()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == "test-session"
    update = call_args[1]["update"]
    assert isinstance(update, AgentThoughtChunk)
    assert update.content.text == "This is my thought"


@pytest.mark.asyncio
async def test_extract_thought_filters_json_syntax(event_subscriber):
    """Test that JSON syntax is filtered out from thought arguments."""
    # These should return None (JSON syntax only)
    assert event_subscriber._extract_thought_from_args("{") is None
    assert event_subscriber._extract_thought_from_args("}") is None
    assert event_subscriber._extract_thought_from_args('"') is None
    assert event_subscriber._extract_thought_from_args('{"thought') is None
    assert event_subscriber._extract_thought_from_args('": "') is None
    assert event_subscriber._extract_thought_from_args('"}') is None

    # These should return the actual thought content
    assert event_subscriber._extract_thought_from_args("Hello world") == "Hello world"
    assert (
        event_subscriber._extract_thought_from_args("I need to think")
        == "I need to think"
    )


@pytest.mark.asyncio
async def test_think_tool_streaming_via_on_token(
    event_subscriber, mock_connection, mock_streaming_chunk
):
    """Test complete think tool streaming through on_token method."""
    chunk, delta = mock_streaming_chunk
    delta.content = None
    delta.reasoning_content = None

    # Create tool calls list with think tool
    tool_call = MagicMock()
    tool_call.index = 0
    tool_call.id = "tool_123"
    function = MagicMock()
    function.name = "think"
    function.arguments = ""
    tool_call.function = function
    delta.tool_calls = [tool_call]

    # Process first chunk (registers think tool)
    event_subscriber.on_token(chunk)

    # Verify think tool is registered
    assert 0 in event_subscriber._streaming_tool_calls
    assert event_subscriber._streaming_tool_calls[0]["is_think"] is True


@pytest.mark.asyncio
async def test_non_think_tool_tracked_for_progress(event_subscriber, mock_tool_call):
    """Test that non-think tools are tracked for ToolCallProgress streaming."""
    tool_call, function = mock_tool_call
    tool_call.id = "tool_456"
    function.name = "terminal"
    function.arguments = None

    # Mock _schedule_async to avoid event loop issues in test
    with patch.object(event_subscriber, "_schedule_async"):
        # Handle the tool call with non-think name
        event_subscriber._handle_tool_call_streaming(tool_call)

    # The index should be tracked but is_think should be False
    assert 0 in event_subscriber._streaming_tool_calls
    assert event_subscriber._streaming_tool_calls[0]["is_think"] is False
    assert event_subscriber._streaming_tool_calls[0]["name"] == "terminal"
    assert event_subscriber._streaming_tool_calls[0]["tool_call_id"] == "tool_456"


@pytest.mark.asyncio
async def test_tool_call_progress_streaming(event_subscriber, mock_connection):
    """Test that non-think tools stream via ToolCallProgress."""
    from acp.schema import ToolCallProgress

    tool_call_id = "tool_789"
    arguments = '{"command": "ls -la"}'

    await event_subscriber._send_tool_call_progress(tool_call_id, arguments)

    # Verify session_update was called with ToolCallProgress
    mock_connection.session_update.assert_called()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == "test-session"
    update = call_args[1]["update"]
    assert isinstance(update, ToolCallProgress)
    assert update.tool_call_id == tool_call_id
    assert update.session_update == "tool_call_update"
    assert update.content is not None
    assert len(update.content) == 1
    assert update.content[0].content.text == arguments


@pytest.mark.asyncio
async def test_multiple_tool_calls_streaming(event_subscriber, mock_streaming_chunk):
    """Test streaming multiple concurrent tool calls."""
    chunk, delta = mock_streaming_chunk
    delta.content = None
    delta.reasoning_content = None

    # Create two tool calls
    tool_call_0 = MagicMock()
    tool_call_0.index = 0
    tool_call_0.id = "tool_think"
    function_0 = MagicMock()
    function_0.name = "think"
    function_0.arguments = ""
    tool_call_0.function = function_0

    tool_call_1 = MagicMock()
    tool_call_1.index = 1
    tool_call_1.id = "tool_terminal"
    function_1 = MagicMock()
    function_1.name = "terminal"
    function_1.arguments = ""
    tool_call_1.function = function_1

    delta.tool_calls = [tool_call_0, tool_call_1]

    # Mock _schedule_async to avoid event loop issues in test
    with patch.object(event_subscriber, "_schedule_async"):
        # Process the chunk
        event_subscriber.on_token(chunk)

    # Both tools should be tracked
    assert 0 in event_subscriber._streaming_tool_calls
    assert 1 in event_subscriber._streaming_tool_calls
    assert event_subscriber._streaming_tool_calls[0]["is_think"] is True
    assert event_subscriber._streaming_tool_calls[1]["is_think"] is False


@pytest.mark.asyncio
async def test_tool_call_id_update(event_subscriber, mock_tool_call):
    """Test that tool call ID can be updated after initial registration."""
    tool_call, function = mock_tool_call
    tool_call.id = None  # ID might come in a later chunk
    function.name = "file_editor"
    function.arguments = None

    # Mock _schedule_async to avoid event loop issues in test
    with patch.object(event_subscriber, "_schedule_async"):
        # Register with name but no ID
        event_subscriber._handle_tool_call_streaming(tool_call)
        assert event_subscriber._streaming_tool_calls[0]["tool_call_id"] is None

        # Update with ID in subsequent chunk
        tool_call.id = "tool_updated_id"
        function.name = None  # Name might be None in subsequent chunks
        event_subscriber._handle_tool_call_streaming(tool_call)

    assert (
        event_subscriber._streaming_tool_calls[0]["tool_call_id"] == "tool_updated_id"
    )


@pytest.mark.asyncio
async def test_tool_call_start_sent_for_non_think_tools(
    event_subscriber, mock_connection
):
    """Test that ToolCallStart is sent when a non-think tool starts streaming."""
    from acp.schema import ToolCallStart

    tool_call_id = "tool_abc"
    tool_name = "terminal"

    await event_subscriber._send_tool_call_start(tool_call_id, tool_name)

    # Verify session_update was called with ToolCallStart
    mock_connection.session_update.assert_called()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == "test-session"
    update = call_args[1]["update"]
    assert isinstance(update, ToolCallStart)
    assert update.tool_call_id == tool_call_id
    assert update.title == tool_name
    assert update.kind == "execute"
    assert update.status == "in_progress"
    assert update.session_update == "tool_call"


@pytest.mark.asyncio
async def test_tool_call_start_triggered_on_first_detection(
    event_subscriber, mock_connection, mock_streaming_chunk
):
    """Test that ToolCallStart is sent only once when tool is first detected."""
    chunk, delta = mock_streaming_chunk
    delta.content = None
    delta.reasoning_content = None

    # First chunk: tool with id and name
    tool_call = MagicMock()
    tool_call.index = 0
    tool_call.id = "tool_xyz"
    function = MagicMock()
    function.name = "terminal"
    function.arguments = ""
    tool_call.function = function
    delta.tool_calls = [tool_call]

    # Mock _schedule_async to avoid event loop issues in test
    with patch.object(event_subscriber, "_schedule_async") as mock_schedule:
        # Process chunk - should trigger ToolCallStart
        event_subscriber.on_token(chunk)

        # Verify _schedule_async was called with _send_tool_call_start coroutine
        assert mock_schedule.called

    # Verify tool is registered and marked as started
    assert 0 in event_subscriber._streaming_tool_calls
    assert event_subscriber._streaming_tool_calls[0]["started"] is True


@pytest.mark.asyncio
async def test_tool_call_start_not_sent_for_think_tool(
    event_subscriber, mock_tool_call
):
    """Test that ToolCallStart is NOT sent for think tools."""
    tool_call, function = mock_tool_call
    tool_call.id = "tool_think_123"
    function.name = "think"
    function.arguments = None

    # Process think tool
    event_subscriber._handle_tool_call_streaming(tool_call)

    # Verify think tool is registered but started should remain False
    # (since we don't send ToolCallStart for think tools)
    assert 0 in event_subscriber._streaming_tool_calls
    assert event_subscriber._streaming_tool_calls[0]["is_think"] is True
    assert event_subscriber._streaming_tool_calls[0]["started"] is False


@pytest.mark.asyncio
async def test_tool_kind_mapping(event_subscriber):
    """Test that tool names are correctly mapped to ToolKind."""
    assert event_subscriber._get_tool_kind_from_name("terminal") == "execute"
    assert event_subscriber._get_tool_kind_from_name("browser_navigate") == "fetch"
    assert event_subscriber._get_tool_kind_from_name("browser_click") == "fetch"
    assert event_subscriber._get_tool_kind_from_name("file_editor") == "edit"
    assert event_subscriber._get_tool_kind_from_name("think") == "think"
    assert event_subscriber._get_tool_kind_from_name("unknown_tool") == "other"


@pytest.mark.asyncio
async def test_tool_call_start_waits_for_id_and_name(event_subscriber, mock_tool_call):
    """Test that ToolCallStart is not sent until both id and name are available."""
    tool_call, function = mock_tool_call

    # First chunk: only name, no id
    tool_call.id = None
    function.name = "terminal"
    function.arguments = None

    # Mock _schedule_async to avoid event loop issues in test
    with patch.object(event_subscriber, "_schedule_async") as mock_schedule:
        event_subscriber._handle_tool_call_streaming(tool_call)

        # Tool should be registered but not started (no id yet)
        assert 0 in event_subscriber._streaming_tool_calls
        assert event_subscriber._streaming_tool_calls[0]["started"] is False
        assert not mock_schedule.called  # Should not have been called yet

        # Second chunk: id arrives
        tool_call.id = "tool_delayed_id"
        function.name = None  # Name might be None in subsequent chunks

        event_subscriber._handle_tool_call_streaming(tool_call)

        # Now started should be True and _schedule_async called
        assert mock_schedule.called

    assert event_subscriber._streaming_tool_calls[0]["started"] is True


@pytest.mark.asyncio
async def test_tool_call_arguments_accumulated(event_subscriber, mock_tool_call):
    """Test that tool call arguments are accumulated across chunks."""
    tool_call, function = mock_tool_call
    tool_call.id = "tool_accum"
    function.name = "terminal"

    with patch.object(event_subscriber, "_schedule_async"):
        # First chunk: register tool
        function.arguments = ""
        event_subscriber._handle_tool_call_streaming(tool_call)
        assert event_subscriber._streaming_tool_calls[0]["accumulated_args"] == ""

        # Second chunk: first argument piece
        tool_call.id = None
        function.name = None
        function.arguments = '{"command'
        event_subscriber._handle_tool_call_streaming(tool_call)
        assert (
            event_subscriber._streaming_tool_calls[0]["accumulated_args"] == '{"command'
        )

        # Third chunk: second argument piece
        function.arguments = '": "ls'
        event_subscriber._handle_tool_call_streaming(tool_call)
        assert (
            event_subscriber._streaming_tool_calls[0]["accumulated_args"]
            == '{"command": "ls'
        )

        # Fourth chunk: final piece
        function.arguments = ' -la"}'
        event_subscriber._handle_tool_call_streaming(tool_call)
        assert (
            event_subscriber._streaming_tool_calls[0]["accumulated_args"]
            == '{"command": "ls -la"}'
        )
