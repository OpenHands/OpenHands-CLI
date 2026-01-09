"""Tests for SharedACPAgentHandler."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from acp import RequestError
from acp.schema import Implementation

from openhands_cli.acp_impl.agent.shared_agent_handler import SharedACPAgentHandler


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def shared_handler(mock_connection):
    """Create a SharedACPAgentHandler instance."""
    return SharedACPAgentHandler(mock_connection)


class TestInitialize:
    """Tests for the initialize method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "agent_configured,expected_auth_count",
        [
            (True, 1),  # Configured: OAuth auth method returned
            (False, 0),  # Not configured: no auth methods
        ],
    )
    async def test_initialize_auth_methods(
        self, shared_handler, agent_configured, expected_auth_count
    ):
        """Test initialize returns correct auth methods based on config."""
        with patch(
            "openhands_cli.acp_impl.agent.shared_agent_handler.load_agent_specs"
        ) as mock_load:
            if agent_configured:
                mock_load.return_value = MagicMock()
            else:
                from openhands_cli.setup import MissingAgentSpec

                mock_load.side_effect = MissingAgentSpec("Not configured")

            response = await shared_handler.initialize(
                protocol_version=1,
                client_info=Implementation(name="test", version="1.0"),
            )

            assert response.protocol_version == 1
            assert len(response.auth_methods) == expected_auth_count
            if expected_auth_count > 0:
                assert response.auth_methods[0].id == "oauth"

    @pytest.mark.asyncio
    async def test_initialize_capabilities(self, shared_handler):
        """Test initialize returns correct capabilities."""
        with patch(
            "openhands_cli.acp_impl.agent.shared_agent_handler.load_agent_specs"
        ):
            response = await shared_handler.initialize(protocol_version=1)

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
    async def test_authenticate_returns_response(self, shared_handler):
        """Test authenticate returns an AuthenticateResponse."""
        response = await shared_handler.authenticate(method_id="any-method")
        assert response is not None


class TestNewSession:
    """Tests for the new_session method."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock agent context."""
        ctx = MagicMock()
        ctx._conn = AsyncMock()
        ctx._running_tasks = {}
        ctx._resume_conversation_id = None
        ctx.agent_type = "local"
        ctx.active_session = {}
        ctx._cleanup_session = MagicMock()
        return ctx

    @pytest.mark.asyncio
    async def test_new_session_creates_uuid(self, shared_handler, mock_context):
        """Test new_session generates a valid UUID session ID."""
        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        mock_context._get_or_create_conversation = AsyncMock(
            return_value=mock_conversation
        )

        response = await shared_handler.new_session(
            ctx=mock_context, mcp_servers=[], working_dir="/tmp"
        )

        # Verify session ID is a valid UUID
        from uuid import UUID

        UUID(response.session_id)  # Will raise if invalid

    @pytest.mark.asyncio
    async def test_new_session_uses_resume_id(self, shared_handler, mock_context):
        """Test new_session uses resume_conversation_id when provided."""
        resume_id = str(uuid4())
        mock_context._resume_conversation_id = resume_id

        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        mock_context._get_or_create_conversation = AsyncMock(
            return_value=mock_conversation
        )

        response = await shared_handler.new_session(
            ctx=mock_context, mcp_servers=[], working_dir="/tmp"
        )

        assert response.session_id == resume_id

        response = await shared_handler.new_session(
            ctx=mock_context, mcp_servers=[], working_dir="/tmp"
        )

        # Resume ID was cleared, new session ID as assigned next time
        assert response.session_id != resume_id

    @pytest.mark.asyncio
    async def test_new_session_returns_modes(self, shared_handler, mock_context):
        """Test new_session returns session modes in response."""
        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        mock_context._get_or_create_conversation = AsyncMock(
            return_value=mock_conversation
        )

        response = await shared_handler.new_session(
            ctx=mock_context, mcp_servers=[], working_dir="/tmp"
        )

        assert response.modes is not None
        assert response.modes.available_modes is not None
        assert len(response.modes.available_modes) == 3

    @pytest.mark.asyncio
    async def test_new_session_replays_events_on_resume(
        self, shared_handler, mock_context
    ):
        """Test new_session replays historic events when resuming."""
        resume_id = str(uuid4())
        mock_context._resume_conversation_id = resume_id

        # Create mock events
        mock_event1 = MagicMock()
        mock_event2 = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.state.events = [mock_event1, mock_event2]
        mock_context._get_or_create_conversation = AsyncMock(
            return_value=mock_conversation
        )

        with patch(
            "openhands_cli.acp_impl.agent.shared_agent_handler.EventSubscriber"
        ) as mock_subscriber_class:
            mock_subscriber = AsyncMock()
            mock_subscriber_class.return_value = mock_subscriber

            await shared_handler.new_session(
                ctx=mock_context, mcp_servers=[], working_dir="/tmp"
            )

            # Verify events were replayed
            assert mock_subscriber.call_count == 2

    @pytest.mark.asyncio
    async def test_new_session_handles_missing_agent_spec(
        self, shared_handler, mock_context
    ):
        """Test new_session raises RequestError when agent not configured."""
        from openhands_cli.setup import MissingAgentSpec

        mock_context._get_or_create_conversation = AsyncMock(
            side_effect=MissingAgentSpec("Not configured")
        )

        with pytest.raises(RequestError) as exc_info:
            await shared_handler.new_session(
                ctx=mock_context, mcp_servers=[], working_dir="/tmp"
            )

        assert exc_info.value.data is not None
        assert "Agent not configured" in exc_info.value.data.get("reason", "")


class TestSetSessionMode:
    """Tests for the set_session_mode method."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock agent context."""
        ctx = MagicMock()
        ctx._conn = AsyncMock()
        ctx.active_session = {}
        return ctx

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mode_id",
        ["always-ask", "always-approve", "llm-approve"],
    )
    async def test_set_session_mode_valid_modes(
        self, shared_handler, mock_context, mode_id
    ):
        """Test set_session_mode accepts all valid modes."""
        session_id = str(uuid4())
        mock_conversation = MagicMock()
        mock_context.active_session[session_id] = mock_conversation

        response = await shared_handler.set_session_mode(
            ctx=mock_context, mode_id=mode_id, session_id=session_id
        )

        assert response is not None
        mock_context._conn.session_update.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invalid_mode",
        ["invalid", "auto", "manual", ""],
    )
    async def test_set_session_mode_invalid_modes(
        self, shared_handler, mock_context, invalid_mode
    ):
        """Test set_session_mode rejects invalid modes."""
        session_id = str(uuid4())

        with pytest.raises(RequestError) as exc_info:
            await shared_handler.set_session_mode(
                ctx=mock_context, mode_id=invalid_mode, session_id=session_id
            )

        assert exc_info.value.data is not None
        assert "Invalid mode ID" in exc_info.value.data.get("reason", "")


class TestCancel:
    """Tests for the cancel method."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock agent context."""
        ctx = MagicMock()
        ctx._running_tasks = {}
        return ctx

    @pytest.mark.asyncio
    async def test_cancel_pauses_conversation(self, shared_handler, mock_context):
        """Test cancel pauses the conversation."""
        session_id = str(uuid4())
        mock_conversation = MagicMock()
        mock_context._get_or_create_conversation = AsyncMock(
            return_value=mock_conversation
        )

        await shared_handler.cancel(ctx=mock_context, session_id=session_id)

        mock_conversation.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_waits_for_running_task(self, shared_handler, mock_context):
        """Test cancel waits for running task to complete."""
        import asyncio

        session_id = str(uuid4())
        mock_conversation = MagicMock()
        mock_context._get_or_create_conversation = AsyncMock(
            return_value=mock_conversation
        )

        # Create a running task
        async def long_running():
            await asyncio.sleep(0.1)

        task = asyncio.create_task(long_running())
        mock_context._running_tasks[session_id] = task

        with patch.object(
            shared_handler, "wait_for_task_completion", new_callable=AsyncMock
        ) as mock_wait:
            await shared_handler.cancel(ctx=mock_context, session_id=session_id)

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
    async def test_list_sessions_returns_empty(self, shared_handler):
        """Test list_sessions returns empty list (no-op for now)."""
        response = await shared_handler.list_sessions()
        assert response.sessions == []


class TestExtMethods:
    """Tests for extension methods."""

    @pytest.mark.asyncio
    async def test_ext_method_returns_error(self, shared_handler):
        """Test ext_method returns error (not supported)."""
        result = await shared_handler.ext_method("test_method", {"key": "value"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_ext_notification_is_noop(self, shared_handler):
        """Test ext_notification completes without error."""
        # Should not raise
        await shared_handler.ext_notification("test_notification", {"key": "value"})
