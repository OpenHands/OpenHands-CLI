"""Common tests for both LocalOpenHandsACPAgent and OpenHandsCloudACPAgent.

These tests verify that both agent implementations behave consistently
for shared functionality. More detailed unit tests for the SharedACPAgentHandler
are in test_shared_agent_handler.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from acp import RequestError

from openhands_cli.acp_impl.agent import LocalOpenHandsACPAgent, OpenHandsCloudACPAgent


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    return AsyncMock()


@pytest.fixture(params=["local", "cloud"])
def agent(request, mock_connection):
    """Parameterized fixture that creates either local or cloud agent."""
    if request.param == "local":
        return LocalOpenHandsACPAgent(mock_connection, "always-ask")
    else:
        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.TokenStorage"
        ) as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.get_api_key.return_value = "test-api-key"
            mock_storage_class.return_value = mock_storage
            return OpenHandsCloudACPAgent(
                conn=mock_connection,
                initial_confirmation_mode="always-ask",
                cloud_api_url="https://app.all-hands.dev",
            )


class TestLoadSession:
    """Tests for load_session - both agents handle session loading consistently."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invalid_session_id",
        ["not-a-uuid", "12345", "invalid-session"],
    )
    async def test_load_session_rejects_invalid_uuid(self, agent, invalid_session_id):
        """Test load_session rejects invalid UUIDs."""
        with pytest.raises(RequestError) as exc_info:
            await agent.load_session(
                cwd="/tmp", mcp_servers=[], session_id=invalid_session_id
            )

        assert exc_info.value.data is not None
        assert "Invalid session ID" in exc_info.value.data.get("reason", "")

    @pytest.mark.asyncio
    async def test_load_session_replays_historic_events(self, agent, mock_connection):
        """Test that load_session replays historic events to the client."""
        from openhands.sdk import Message, TextContent
        from openhands.sdk.event.llm_convertible.message import MessageEvent

        session_id = str(uuid4())

        mock_event1 = MessageEvent(
            source="user",
            llm_message=Message(role="user", content=[TextContent(text="Hello")]),
        )
        mock_event2 = MessageEvent(
            source="agent",
            llm_message=Message(
                role="assistant", content=[TextContent(text="Hi there!")]
            ),
        )

        mock_conversation = MagicMock()
        mock_conversation.state.events = [mock_event1, mock_event2]
        agent._active_sessions[session_id] = mock_conversation

        if isinstance(agent, OpenHandsCloudACPAgent):
            agent._active_workspaces[session_id] = MagicMock()

        # EventSubscriber is imported in base_agent for local agent's load_session
        # and in remote_agent for cloud agent's load_session override
        patch_path = (
            "openhands_cli.acp_impl.agent.remote_agent.EventSubscriber"
            if isinstance(agent, OpenHandsCloudACPAgent)
            else "openhands_cli.acp_impl.agent.base_agent.EventSubscriber"
        )

        with patch(patch_path) as mock_subscriber_class:
            mock_subscriber = AsyncMock()
            mock_subscriber_class.return_value = mock_subscriber

            response = await agent.load_session(
                cwd="/tmp", mcp_servers=[], session_id=session_id
            )

            assert response is not None
            assert response.modes is not None
            mock_subscriber_class.assert_called_once_with(session_id, mock_connection)
            assert mock_subscriber.call_count == 2

    @pytest.mark.asyncio
    async def test_load_session_includes_modes(self, agent):
        """Test that load_session returns modes in response."""
        session_id = str(uuid4())

        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        agent._active_sessions[session_id] = mock_conversation

        if isinstance(agent, OpenHandsCloudACPAgent):
            agent._active_workspaces[session_id] = MagicMock()

        response = await agent.load_session(
            cwd="/tmp", mcp_servers=[], session_id=session_id
        )

        assert response is not None
        assert response.modes is not None
        assert response.modes.current_mode_id == "always-ask"
        assert len(response.modes.available_modes) == 3
        mode_ids = {mode.id for mode in response.modes.available_modes}
        assert mode_ids == {"always-ask", "always-approve", "llm-approve"}


class TestSetSessionMode:
    """Tests for set_session_mode - both agents handle mode changes consistently."""

    @pytest.mark.asyncio
    async def test_set_session_mode_invalid(self, agent):
        """Test setting session mode with invalid mode ID."""
        with pytest.raises(RequestError):
            await agent.set_session_mode(mode_id="invalid", session_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_set_session_mode_updates_confirmation_policy(self, agent):
        """Test that setting mode updates conversation's confirmation policy."""
        from openhands.sdk.security.confirmation_policy import (
            AlwaysConfirm,
            NeverConfirm,
        )

        session_id = str(uuid4())
        mock_conversation = MagicMock()
        mock_conversation.state.confirmation_policy = AlwaysConfirm()
        mock_conversation.state.events = []

        def set_policy_side_effect(new_policy):
            mock_conversation.state.confirmation_policy = new_policy

        mock_conversation.set_confirmation_policy = MagicMock(
            side_effect=set_policy_side_effect
        )
        mock_conversation.set_security_analyzer = MagicMock()
        agent._active_sessions[session_id] = mock_conversation

        if isinstance(agent, OpenHandsCloudACPAgent):
            agent._active_workspaces[session_id] = MagicMock()

        await agent.set_session_mode(mode_id="always-approve", session_id=session_id)

        mock_conversation.set_confirmation_policy.assert_called()
        last_policy = mock_conversation.set_confirmation_policy.call_args[0][0]
        assert isinstance(last_policy, NeverConfirm)


class TestCancel:
    """Tests for cancel - ensures both agents handle cancellation consistently."""

    @pytest.mark.asyncio
    async def test_cancel_pauses_conversation(self, agent):
        """Test that cancel pauses the conversation."""
        session_id = str(uuid4())
        mock_conversation = MagicMock()
        agent._active_sessions[session_id] = mock_conversation

        if isinstance(agent, OpenHandsCloudACPAgent):
            agent._active_workspaces[session_id] = MagicMock()

        await agent.cancel(session_id=session_id)

        mock_conversation.pause.assert_called_once()
