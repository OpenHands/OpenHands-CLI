"""Tests for BaseOpenHandsACPAgent methods (previously in SharedACPAgentHandler)."""

import asyncio
from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from acp import RequestError
from acp.schema import Implementation

from openhands.sdk import BaseConversation
from openhands_cli.acp_impl.agent.base_agent import BaseOpenHandsACPAgent
from openhands_cli.acp_impl.agent.util import AgentType
from openhands_cli.acp_impl.confirmation import ConfirmationMode


class ConcreteTestAgent(BaseOpenHandsACPAgent):
    """Concrete implementation of BaseOpenHandsACPAgent for testing."""

    def __init__(
        self,
        conn,
        initial_confirmation_mode: ConfirmationMode = "always-ask",
        resume_conversation_id: str | None = None,
    ):
        super().__init__(conn, initial_confirmation_mode, resume_conversation_id)
        self._mock_conversation: BaseConversation | None = None

    @property
    def agent_type(self) -> AgentType:
        return "local"

    @property
    def active_session(self) -> Mapping[str, BaseConversation]:
        return self._active_sessions

    async def _get_or_create_conversation(
        self,
        session_id: str,
        working_dir: str | None = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
        is_resuming: bool = False,
    ) -> BaseConversation:
        if self._mock_conversation:
            self._active_sessions[session_id] = self._mock_conversation
            return self._mock_conversation
        raise NotImplementedError("Set _mock_conversation before calling")

    def _cleanup_session(self, session_id: str) -> None:
        self._active_sessions.pop(session_id, None)

    async def _is_authenticated(self) -> bool:
        return True


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def test_agent(mock_connection):
    """Create a ConcreteTestAgent instance."""
    return ConcreteTestAgent(mock_connection)


class TestInitialize:
    """Tests for the initialize method."""

    @pytest.mark.asyncio
    async def test_initialize_auth_methods(self, test_agent):
        """Test initialize always returns auth method."""
        response = await test_agent.initialize(
            protocol_version=1,
            client_info=Implementation(name="test", version="1.0"),
        )

        assert response.protocol_version == 1
        # Auth methods are always returned
        assert len(response.auth_methods) == 1
        assert response.auth_methods[0].id == "oauth"
        assert response.auth_methods[0].field_meta == {"type": "agent"}

    @pytest.mark.asyncio
    async def test_initialize_capabilities(self, test_agent):
        """Test initialize returns correct capabilities."""
        response = await test_agent.initialize(protocol_version=1)

        # Check agent capabilities
        caps = response.agent_capabilities
        assert caps.load_session is True
        assert caps.mcp_capabilities.http is True
        assert caps.mcp_capabilities.sse is True
        assert caps.prompt_capabilities.image is True
        assert caps.prompt_capabilities.embedded_context is True
        assert caps.prompt_capabilities.audio is False


class TestAuthenticate:
    """Tests for the authenticate method."""

    @pytest.mark.asyncio
    async def test_authenticate_returns_response(self, test_agent):
        """Test authenticate returns an AuthenticateResponse for OAuth method."""
        with patch(
            "openhands_cli.auth.login_command.login_command",
            new_callable=AsyncMock,
        ):
            response = await test_agent.authenticate(method_id="oauth")
            assert response is not None

    @pytest.mark.asyncio
    async def test_authenticate_rejects_invalid_method(self, test_agent):
        """Test authenticate rejects invalid method IDs."""
        with pytest.raises(RequestError) as exc_info:
            await test_agent.authenticate(method_id="invalid-method")

        assert exc_info.value.data is not None
        assert "Unsupported authentication method" in exc_info.value.data.get(
            "reason", ""
        )


class TestBaseAgentHelpers:
    """Tests for the focused helper methods extracted from BaseOpenHandsACPAgent."""

    @pytest.mark.asyncio
    async def test_send_agent_text_chunk_sends_text_update(self, test_agent):
        """_send_agent_text_chunk should wrap plain text in an ACP text update."""
        session_id = str(uuid4())

        await test_agent._send_agent_text_chunk(session_id, "Hello from helper")

        test_agent._conn.session_update.assert_awaited_once()
        call_kwargs = test_agent._conn.session_update.await_args.kwargs
        assert call_kwargs["session_id"] == session_id
        assert call_kwargs["update"].session_update == "agent_message_chunk"
        assert call_kwargs["update"].content.text == "Hello from helper"

    @pytest.mark.asyncio
    async def test_handle_slash_command_help_sends_help_text(self, test_agent):
        """_handle_slash_command should send a help response to the client."""
        session_id = str(uuid4())

        response = await test_agent._handle_slash_command(
            session_id=session_id,
            command="help",
            argument="",
        )

        assert response.stop_reason == "end_turn"
        call_kwargs = test_agent._conn.session_update.await_args.kwargs
        assert call_kwargs["session_id"] == session_id
        assert "Available slash commands" in call_kwargs["update"].content.text

    @pytest.mark.asyncio
    async def test_run_conversation_task_cleans_up_task_after_error(self, test_agent):
        """_run_conversation_task should always clean up its tracking entry."""
        session_id = str(uuid4())
        mock_conversation = MagicMock()

        async def failing_runner(*, conversation, conn, session_id: str):
            assert conversation is mock_conversation
            assert conn is test_agent._conn
            assert session_id in test_agent._running_tasks
            raise RuntimeError("runner failed")

        with patch(
            "openhands_cli.acp_impl.agent.base_agent.run_conversation_with_confirmation",
            side_effect=failing_runner,
        ) as mock_runner:
            with pytest.raises(RuntimeError, match="runner failed"):
                await test_agent._run_conversation_task(session_id, mock_conversation)

        mock_runner.assert_awaited_once_with(
            conversation=mock_conversation,
            conn=test_agent._conn,
            session_id=session_id,
        )
        assert session_id not in test_agent._running_tasks

    @pytest.mark.asyncio
    async def test_replay_conversation_events_streams_real_events(self, test_agent):
        """_replay_conversation_events should stream real agent messages."""
        from openhands.sdk import Message, TextContent
        from openhands.sdk.event.llm_convertible.message import MessageEvent

        session_id = str(uuid4())
        events = [
            MessageEvent(
                source="agent",
                llm_message=Message(
                    role="assistant",
                    content=[TextContent(text="First reply")],
                ),
            ),
            MessageEvent(
                source="agent",
                llm_message=Message(
                    role="assistant",
                    content=[TextContent(text="Second reply")],
                ),
            ),
        ]

        await test_agent._replay_conversation_events(
            session_id=session_id,
            events=events,
            context="for testing",
        )

        assert test_agent._conn.session_update.await_count == len(events)
        updates = [
            call.kwargs["update"]
            for call in test_agent._conn.session_update.await_args_list
        ]
        assert [update.content.text for update in updates] == [
            "First reply",
            "Second reply",
        ]


class TestNewSession:
    """Tests for the new_session method."""

    @pytest.mark.asyncio
    async def test_new_session_creates_uuid(self, test_agent):
        """Test new_session generates a valid UUID session ID."""
        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        test_agent._mock_conversation = mock_conversation

        response = await test_agent.new_session(cwd="/tmp", mcp_servers=[])

        # Verify session ID is a valid UUID
        from uuid import UUID

        UUID(response.session_id)  # Will raise if invalid

    @pytest.mark.asyncio
    async def test_new_session_uses_resume_id(self, mock_connection):
        """Test new_session uses resume_conversation_id when provided."""
        resume_id = str(uuid4())
        agent = ConcreteTestAgent(mock_connection, resume_conversation_id=resume_id)

        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        agent._mock_conversation = mock_conversation

        response = await agent.new_session(cwd="/tmp", mcp_servers=[])
        assert response.session_id == resume_id

        response = await agent.new_session(cwd="/tmp", mcp_servers=[])
        # Resume ID was cleared, new session ID assigned next time
        assert response.session_id != resume_id

    @pytest.mark.asyncio
    async def test_new_session_returns_modes(self, test_agent):
        """Test new_session returns session modes in response."""
        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        test_agent._mock_conversation = mock_conversation

        response = await test_agent.new_session(cwd="/tmp", mcp_servers=[])

        assert response.modes is not None
        assert response.modes.available_modes is not None
        assert len(response.modes.available_modes) == 3

    @pytest.mark.asyncio
    async def test_new_session_replays_events_on_resume(self, mock_connection):
        """Test new_session replays historic events when resuming."""
        resume_id = str(uuid4())
        agent = ConcreteTestAgent(mock_connection, resume_conversation_id=resume_id)

        # Create mock events
        mock_event1 = MagicMock()
        mock_event2 = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.state.events = [mock_event1, mock_event2]
        agent._mock_conversation = mock_conversation

        with patch(
            "openhands_cli.acp_impl.agent.base_agent.EventSubscriber"
        ) as mock_subscriber_class:
            mock_subscriber = AsyncMock()
            mock_subscriber_class.return_value = mock_subscriber

            await agent.new_session(cwd="/tmp", mcp_servers=[])

            # Verify events were replayed
            assert mock_subscriber.call_count == 2

    @pytest.mark.asyncio
    async def test_new_session_handles_missing_agent_spec(self, mock_connection):
        """Test new_session raises RequestError when agent not configured."""
        from openhands_cli.setup import MissingAgentSpec

        agent = ConcreteTestAgent(mock_connection)
        # Override _get_or_create_conversation to raise MissingAgentSpec
        agent._get_or_create_conversation = AsyncMock(
            side_effect=MissingAgentSpec("Not configured")
        )

        with pytest.raises(RequestError) as exc_info:
            await agent.new_session(cwd="/tmp", mcp_servers=[])

        assert exc_info.value.data is not None
        assert "Agent not configured" in exc_info.value.data.get("reason", "")


class TestSetSessionMode:
    """Tests for the set_session_mode method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mode_id",
        ["always-ask", "always-approve", "llm-approve"],
    )
    async def test_set_session_mode_valid_modes(self, test_agent, mode_id):
        """Test set_session_mode accepts all valid modes."""
        session_id = str(uuid4())
        mock_conversation = MagicMock()
        test_agent._active_sessions[session_id] = mock_conversation

        response = await test_agent.set_session_mode(
            mode_id=mode_id, session_id=session_id
        )

        assert response is not None
        test_agent._conn.session_update.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invalid_mode",
        ["invalid", "auto", "manual", ""],
    )
    async def test_set_session_mode_invalid_modes(self, test_agent, invalid_mode):
        """Test set_session_mode rejects invalid modes."""
        session_id = str(uuid4())

        with pytest.raises(RequestError) as exc_info:
            await test_agent.set_session_mode(
                mode_id=invalid_mode, session_id=session_id
            )

        assert exc_info.value.data is not None
        assert "Invalid mode ID" in exc_info.value.data.get("reason", "")


class TestCancel:
    """Tests for the cancel method."""

    @pytest.mark.asyncio
    async def test_cancel_pauses_conversation(self, test_agent):
        """Test cancel pauses the conversation."""
        session_id = str(uuid4())
        mock_conversation = MagicMock()
        test_agent._mock_conversation = mock_conversation

        await test_agent.cancel(session_id=session_id)

        mock_conversation.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_waits_for_running_task(self, test_agent):
        """Test cancel waits for running task to complete."""
        session_id = str(uuid4())
        mock_conversation = MagicMock()
        test_agent._mock_conversation = mock_conversation

        # Create a running task
        async def long_running():
            await asyncio.sleep(0.1)

        task = asyncio.create_task(long_running())
        test_agent._running_tasks[session_id] = task

        with patch.object(
            test_agent, "_wait_for_task_completion", new_callable=AsyncMock
        ) as mock_wait:
            await test_agent.cancel(session_id=session_id)

            mock_wait.assert_called_once_with(task, session_id)

        # Clean up
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class TestListSessions:
    """Tests for the list_sessions method."""

    @pytest.mark.asyncio
    async def test_list_sessions_returns_empty(self, test_agent):
        """Test list_sessions returns empty list (no-op for now)."""
        response = await test_agent.list_sessions()
        assert response.sessions == []


class TestExtMethods:
    """Tests for extension methods."""

    @pytest.mark.asyncio
    async def test_ext_method_returns_error(self, test_agent):
        """Test ext_method returns error (not supported)."""
        result = await test_agent.ext_method("test_method", {"key": "value"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_ext_notification_is_noop(self, test_agent):
        """Test ext_notification completes without error."""
        # Should not raise
        await test_agent.ext_notification("test_notification", {"key": "value"})
