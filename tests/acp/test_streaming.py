"""Tests for LLM streaming functionality in ACP implementation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from acp.schema import AgentMessageChunk, TextContentBlock
from litellm.types.utils import ModelResponseStream

from openhands_cli.acp_impl.agent import OpenHandsACPAgent


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
def mock_streaming_chunk():
    """Create a mock streaming chunk."""
    chunk = MagicMock(spec=ModelResponseStream)
    choice = MagicMock()
    delta = MagicMock()
    choice.delta = delta
    chunk.choices = [choice]
    return chunk, delta


@pytest.mark.asyncio
async def test_token_callback_creation(acp_agent):
    """Test that token callback is created correctly."""
    session_id = str(uuid4())
    callback = acp_agent._create_token_callback(session_id)

    assert callable(callback)
    assert session_id in acp_agent._streaming_states
    assert acp_agent._streaming_states[session_id] is None


@pytest.mark.asyncio
async def test_streaming_regular_content(
    acp_agent, mock_connection, mock_streaming_chunk
):
    """Test streaming regular content tokens."""
    session_id = str(uuid4())
    chunk, delta = mock_streaming_chunk

    # Set up delta with regular content
    delta.content = "Hello world"
    delta.reasoning_content = None
    delta.tool_calls = None

    # Create callback and process chunk
    callback = acp_agent._create_token_callback(session_id)
    callback(chunk)

    # Wait for async task to complete
    await asyncio.sleep(0.1)

    # Verify session_update was called with AgentMessageChunk
    mock_connection.session_update.assert_called()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == session_id
    update = call_args[1]["update"]
    assert isinstance(update, AgentMessageChunk)
    assert update.session_update == "agent_message_chunk"
    assert isinstance(update.content, TextContentBlock)
    assert update.content.text == "Hello world"


@pytest.mark.asyncio
async def test_streaming_reasoning_content(
    acp_agent, mock_connection, mock_streaming_chunk
):
    """Test streaming reasoning content tokens."""
    session_id = str(uuid4())
    chunk, delta = mock_streaming_chunk

    # Set up delta with reasoning content
    delta.content = None
    delta.reasoning_content = "I need to think about this..."
    delta.tool_calls = None

    # Create callback and process chunk
    callback = acp_agent._create_token_callback(session_id)
    callback(chunk)

    # Wait for async task to complete
    await asyncio.sleep(0.1)

    # Verify session_update was called with formatted reasoning content
    mock_connection.session_update.assert_called()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == session_id
    update = call_args[1]["update"]
    assert isinstance(update, AgentMessageChunk)
    assert "**Reasoning**: I need to think about this..." in update.content.text


@pytest.mark.asyncio
async def test_streaming_tool_calls(acp_agent, mock_connection, mock_streaming_chunk):
    """Test streaming tool call tokens."""
    session_id = str(uuid4())
    chunk, delta = mock_streaming_chunk

    # Set up delta with tool calls
    tool_call = MagicMock()
    tool_call.function.name = "file_editor"
    tool_call.function.arguments = '{"path": "/test.py"}'

    delta.content = None
    delta.reasoning_content = None
    delta.tool_calls = [tool_call]

    # Create callback and process chunk
    callback = acp_agent._create_token_callback(session_id)
    callback(chunk)

    # Wait for async tasks to complete
    await asyncio.sleep(0.1)

    # Verify session_update was called multiple times (tool name and args)
    assert mock_connection.session_update.call_count >= 1

    # Check that tool name was sent
    calls = mock_connection.session_update.call_args_list
    tool_name_call = next(
        call
        for call in calls
        if "**Tool**: file_editor" in call[1]["update"].content.text
    )
    assert tool_name_call is not None


@pytest.mark.asyncio
async def test_streaming_state_tracking(acp_agent, mock_streaming_chunk):
    """Test that streaming state is tracked correctly."""
    session_id = str(uuid4())
    chunk, delta = mock_streaming_chunk

    # Initially no state
    assert session_id not in acp_agent._streaming_states

    # Create callback
    callback = acp_agent._create_token_callback(session_id)
    assert acp_agent._streaming_states[session_id] is None

    # Process content chunk
    delta.content = "test"
    delta.reasoning_content = None
    delta.tool_calls = None
    callback(chunk)

    # State should be updated to "content"
    assert acp_agent._streaming_states[session_id] == "content"

    # Process reasoning chunk
    delta.content = None
    delta.reasoning_content = "thinking"
    delta.tool_calls = None
    callback(chunk)

    # State should be updated to "thinking"
    assert acp_agent._streaming_states[session_id] == "thinking"


@pytest.mark.asyncio
async def test_streaming_state_cleanup_on_cancel(acp_agent, mock_connection):
    """Test that streaming state is cleaned up when session is cancelled."""
    session_id = str(uuid4())

    # Set up mocks
    with patch.object(acp_agent, "_get_or_create_conversation") as mock_get_conv:
        mock_conversation = MagicMock()
        mock_get_conv.return_value = mock_conversation

        # Create streaming state
        acp_agent._streaming_states[session_id] = "content"

        # Cancel session
        await acp_agent.cancel(session_id)

        # Verify state was cleaned up
        assert session_id not in acp_agent._streaming_states


@pytest.mark.asyncio
async def test_streaming_error_handling(acp_agent, mock_connection):
    """Test that streaming errors are handled gracefully."""
    session_id = str(uuid4())

    # Create a callback
    callback = acp_agent._create_token_callback(session_id)

    # Create a malformed chunk that will cause an error
    bad_chunk = MagicMock()
    bad_chunk.choices = None  # This should cause an error

    # Process the bad chunk - should not raise an exception
    try:
        callback(bad_chunk)
        # Wait a bit for any async tasks
        await asyncio.sleep(0.1)
    except Exception as e:
        pytest.fail(f"Token callback should handle errors gracefully, but raised: {e}")


@pytest.mark.asyncio
async def test_conversation_setup_enables_streaming(acp_agent):
    """Test that conversation setup enables streaming on the LLM."""
    session_id = str(uuid4())

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load_specs,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conversation_class,
        patch("openhands_cli.acp_impl.agent.EventSubscriber"),
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

        # Call the method
        acp_agent._setup_acp_conversation(session_id)

        # Verify that streaming was enabled on the LLM
        mock_llm.model_copy.assert_called_once_with(update={"stream": True})

        # Verify that agent was updated with streaming-enabled LLM
        mock_agent.model_copy.assert_called_once_with(update={"llm": mock_updated_llm})

        # Verify that Conversation was created with token_callbacks
        mock_conversation_class.assert_called_once()
        call_kwargs = mock_conversation_class.call_args[1]
        assert "token_callbacks" in call_kwargs
        assert len(call_kwargs["token_callbacks"]) == 1
        assert callable(call_kwargs["token_callbacks"][0])


@pytest.mark.asyncio
async def test_send_streaming_chunk_regular_content(acp_agent, mock_connection):
    """Test sending regular streaming chunk."""
    session_id = str(uuid4())
    content = "Hello world"

    await acp_agent._send_streaming_chunk(session_id, content, is_reasoning=False)

    # Verify session_update was called correctly
    mock_connection.session_update.assert_called_once()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == session_id
    update = call_args[1]["update"]
    assert isinstance(update, AgentMessageChunk)
    assert update.content.text == "Hello world"


@pytest.mark.asyncio
async def test_send_streaming_chunk_reasoning_content(acp_agent, mock_connection):
    """Test sending reasoning streaming chunk."""
    session_id = str(uuid4())
    content = "I need to analyze this"

    await acp_agent._send_streaming_chunk(session_id, content, is_reasoning=True)

    # Verify session_update was called correctly
    mock_connection.session_update.assert_called_once()
    call_args = mock_connection.session_update.call_args

    assert call_args[1]["session_id"] == session_id
    update = call_args[1]["update"]
    assert isinstance(update, AgentMessageChunk)
    assert update.content.text == "**Reasoning**: I need to analyze this"


@pytest.mark.asyncio
async def test_send_streaming_chunk_error_handling(acp_agent, mock_connection):
    """Test that streaming chunk sending handles errors gracefully."""
    session_id = str(uuid4())
    content = "test content"

    # Make session_update raise an exception
    mock_connection.session_update.side_effect = Exception("Connection error")

    # Should not raise an exception
    try:
        await acp_agent._send_streaming_chunk(session_id, content)
    except Exception as e:
        pytest.fail(
            f"_send_streaming_chunk should handle errors gracefully, but raised: {e}"
        )


@pytest.mark.asyncio
async def test_event_subscriber_streaming_enabled(acp_agent):
    """Test that EventSubscriber is created with streaming_enabled=True."""
    session_id = str(uuid4())

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load_specs,
        patch("openhands_cli.acp_impl.agent.Conversation"),
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

        # Call the method
        acp_agent._setup_acp_conversation(session_id)

        # Verify that EventSubscriber was created with streaming_enabled=True
        mock_event_subscriber_class.assert_called_once()
        call_args = mock_event_subscriber_class.call_args
        assert call_args[0][0] == session_id  # session_id
        assert call_args[0][1] == acp_agent._conn  # conn
        assert call_args[1]["streaming_enabled"] is True  # streaming_enabled kwarg
