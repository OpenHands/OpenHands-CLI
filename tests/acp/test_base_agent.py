"""Tests for BaseOpenHandsACPAgent methods (previously in SharedACPAgentHandler)."""

import asyncio
from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from acp import RequestError
from acp.schema import Implementation, LoadSessionResponse

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
    async def test_new_session_returns_modes_and_config_options(self, test_agent):
        """Test new_session returns session modes and schema-driven config options."""
        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        test_agent._mock_conversation = mock_conversation

        response = await test_agent.new_session(cwd="/tmp", mcp_servers=[])

        assert response.modes is not None
        assert response.modes.available_modes is not None
        assert len(response.modes.available_modes) == 3
        assert response.config_options is not None
        config_options = {
            option.model_dump()["id"]: option.model_dump()
            for option in response.config_options
        }
        assert "enable_default_condenser" in config_options
        assert config_options["enable_default_condenser"]["description"] is not None
        assert config_options["enable_default_condenser"]["category"] == "Condenser"
        assert "llm_model" not in config_options

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


class TestSetConfigOption:
    """Tests for schema-driven config option updates."""

    @pytest.mark.asyncio
    async def test_set_config_option_routes_to_programmatic_settings(self, test_agent):
        """Test set_config_option uses SDK-driven field metadata to update settings."""
        with (
            patch(
                "openhands_cli.acp_impl.agent.base_agent.handle_programmatic_setting_command",
                return_value="updated",
            ) as mock_handle,
            patch.object(test_agent, "_get_session_config_options", return_value=[]),
        ):
            response = await test_agent.set_config_option(
                config_id="enable_default_condenser",
                session_id=str(uuid4()),
                value="false",
            )

        mock_handle.assert_called_once_with("condenser", "false")
        assert response is not None
        assert response.config_options == []


class TestResumeAndForkSession:
    """Tests for additional ACP session lifecycle methods."""

    @pytest.mark.asyncio
    async def test_resume_session_delegates_to_load_session(self, test_agent):
        """Test resume_session reuses load_session state replay behavior."""
        load_response = LoadSessionResponse(config_options=[])
        session_id = str(uuid4())

        with patch.object(
            test_agent,
            "load_session",
            new=AsyncMock(return_value=load_response),
        ) as mock_load_session:
            response = await test_agent.resume_session(
                cwd="/tmp",
                session_id=session_id,
                mcp_servers=[],
            )

        mock_load_session.assert_awaited_once_with(
            cwd="/tmp",
            session_id=session_id,
            mcp_servers=[],
        )
        assert response.config_options == []

    @pytest.mark.asyncio
    async def test_fork_session_is_not_supported(self, test_agent):
        """Test fork_session returns a clear unsupported-method error."""
        with pytest.raises(RequestError) as exc_info:
            await test_agent.fork_session(
                cwd="/tmp",
                session_id=str(uuid4()),
                mcp_servers=[],
            )

        assert exc_info.value.data is not None
        assert "fork_session is not supported" in exc_info.value.data.get("reason", "")


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
