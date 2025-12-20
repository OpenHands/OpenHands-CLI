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
    return EventSubscriber("test-session", mock_connection)


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
async def test_token_callback_creation(event_subscriber):
    """Test that token callback is created correctly."""
    loop = asyncio.get_event_loop()
    callback = event_subscriber.create_token_callback(loop)

    assert callable(callback)


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

    # Create callback and process chunk
    loop = asyncio.get_event_loop()
    callback = event_subscriber.create_token_callback(loop)
    callback(chunk)

    # Wait for async task to complete
    await asyncio.sleep(0.1)

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

    # Create callback and process chunk
    loop = asyncio.get_event_loop()
    callback = event_subscriber.create_token_callback(loop)
    callback(chunk)

    # Wait for async task to complete
    await asyncio.sleep(0.1)

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
    loop = asyncio.get_event_loop()
    callback = event_subscriber.create_token_callback(loop)

    # Create a malformed chunk that will cause an error
    bad_chunk = MagicMock()
    bad_chunk.choices = None  # This should cause an error

    # Process the bad chunk - should raise RequestError due to our implementation
    with pytest.raises(Exception):  # Should raise RequestError.internal_error
        callback(bad_chunk)


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
        mock_subscriber.create_token_callback.return_value = MagicMock()
        mock_event_subscriber_class.return_value = mock_subscriber

        # Call the method
        acp_agent._setup_acp_conversation(session_id)

        # Verify that streaming was enabled on the LLM
        mock_llm.model_copy.assert_called_once_with(update={"stream": True})

        # Verify that agent was updated with streaming-enabled LLM
        mock_agent.model_copy.assert_called_once_with(update={"llm": mock_updated_llm})

        # Verify that EventSubscriber was created
        mock_event_subscriber_class.assert_called_once_with(session_id, acp_agent._conn)

        # Verify that token callback was created from EventSubscriber
        mock_subscriber.create_token_callback.assert_called_once()

        # Verify that Conversation was created with token_callbacks
        mock_conversation_class.assert_called_once()
        call_kwargs = mock_conversation_class.call_args[1]
        assert "token_callbacks" in call_kwargs
        assert len(call_kwargs["token_callbacks"]) == 1
        assert callable(call_kwargs["token_callbacks"][0])


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
