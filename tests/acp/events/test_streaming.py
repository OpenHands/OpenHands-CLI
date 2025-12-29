"""Tests for LLM streaming functionality in ACP implementation."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from litellm.types.utils import ModelResponseStream

from openhands_cli.acp_impl.agent import OpenHandsACPAgent
from openhands_cli.acp_impl.events.event import EventSubscriber


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
def acp_agent_with_streaming(mock_connection):
    """Create an OpenHands ACP agent instance with streaming enabled."""
    return OpenHandsACPAgent(mock_connection, "always-ask", streaming_enabled=True)


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


@pytest.fixture
def mock_tool_call():
    """Create a mock tool call for streaming."""
    tool_call = MagicMock()
    tool_call.index = 0
    function = MagicMock()
    tool_call.function = function
    return tool_call, function


@pytest.mark.asyncio
async def test_conversation_setup_enables_streaming(acp_agent_with_streaming, tmp_path):
    """Test that conversation setup enables streaming on the LLM when appropriate."""
    session_id = str(uuid4())

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load_specs,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conversation_class,
        patch(
            "openhands_cli.acp_impl.agent.EventSubscriber"
        ) as mock_event_subscriber_class,
    ):
        # Mock agent with LLM that doesn't use responses API (supports streaming)
        mock_agent = MagicMock()
        mock_llm = MagicMock()
        mock_llm.uses_responses_api.return_value = False  # Streaming should be enabled
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
        mock_event_subscriber_class.return_value = mock_subscriber

        # Mock conversation instance
        mock_conversation = MagicMock()
        mock_conversation_class.return_value = mock_conversation

        # Call the method (agent has streaming_enabled=True)
        acp_agent_with_streaming._setup_acp_conversation(
            session_id, working_dir=str(tmp_path)
        )

        # Verify that streaming was enabled on the LLM
        mock_llm.model_copy.assert_called_once_with(update={"stream": True})

        # Verify that agent was updated with streaming-enabled LLM
        mock_agent.model_copy.assert_called_once_with(update={"llm": mock_updated_llm})

        # Verify that EventSubscriber was created (no loop parameter anymore)
        mock_event_subscriber_class.assert_called_once()
        call_args = mock_event_subscriber_class.call_args
        assert call_args[0][0] == session_id  # session_id
        assert call_args[0][1] == acp_agent_with_streaming._conn  # conn

        # Verify that Conversation was created
        mock_conversation_class.assert_called_once()


@pytest.mark.asyncio
async def test_conversation_setup_without_streaming_flag(acp_agent, tmp_path):
    """Test that conversation setup does NOT enable streaming when flag is False."""
    session_id = str(uuid4())

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load_specs,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conversation_class,
        patch(
            "openhands_cli.acp_impl.agent.EventSubscriber"
        ) as mock_event_subscriber_class,
    ):
        # Mock agent with LLM that doesn't use responses API (supports streaming)
        mock_agent = MagicMock()
        mock_llm = MagicMock()
        mock_llm.uses_responses_api.return_value = False  # Would support streaming
        mock_agent.llm = mock_llm
        mock_load_specs.return_value = mock_agent

        # Mock EventSubscriber instance
        mock_subscriber = MagicMock()
        mock_event_subscriber_class.return_value = mock_subscriber

        # Mock conversation instance
        mock_conversation = MagicMock()
        mock_conversation_class.return_value = mock_conversation

        # Call the method (agent has streaming_enabled=False by default)
        acp_agent._setup_acp_conversation(session_id, working_dir=str(tmp_path))

        # Verify that streaming was NOT enabled on the LLM (no model_copy call)
        mock_llm.model_copy.assert_not_called()

        # Verify that agent was NOT updated
        mock_agent.model_copy.assert_not_called()

        # Verify that Conversation was created without token_callbacks
        mock_conversation_class.assert_called_once()
        call_kwargs = mock_conversation_class.call_args[1]
        assert call_kwargs.get("token_callbacks") is None
