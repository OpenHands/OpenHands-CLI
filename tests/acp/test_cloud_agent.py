"""Tests for OpenHandsCloudACPAgent."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from acp import RequestError
from acp.schema import TextContentBlock

from openhands_cli.acp_impl.agent import OpenHandsCloudACPAgent


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    return AsyncMock()


@pytest.fixture
def cloud_agent(mock_connection):
    """Create an OpenHands Cloud ACP agent instance."""
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


class TestNewSessionAuthentication:
    """Tests for new_session authentication requirements."""

    @pytest.mark.asyncio
    async def test_new_session_raises_auth_required_when_not_authenticated(
        self, mock_connection
    ):
        """Test that new_session raises auth_required when user is not authenticated."""
        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.TokenStorage"
        ) as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.get_api_key.return_value = None
            mock_storage_class.return_value = mock_storage

            agent = OpenHandsCloudACPAgent(
                conn=mock_connection, initial_confirmation_mode="always-ask"
            )

            with pytest.raises(RequestError) as exc_info:
                await agent.new_session(cwd="/tmp", mcp_servers=[])

            assert "Authentication required" in str(exc_info.value.data)

    @pytest.mark.asyncio
    async def test_new_session_proceeds_when_authenticated(self, cloud_agent):
        """Test that new_session proceeds when user is authenticated."""
        with (
            patch(
                "openhands_cli.acp_impl.agent.remote_agent.is_token_valid",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch.object(
                cloud_agent._shared_handler, "new_session", new_callable=AsyncMock
            ) as mock_new_session,
        ):
            mock_response = MagicMock()
            mock_new_session.return_value = mock_response

            result = await cloud_agent.new_session(cwd="/tmp", mcp_servers=[])

            mock_new_session.assert_called_once()
            assert result == mock_response


class TestAuthenticate:
    """Tests for the authenticate method."""

    @pytest.mark.asyncio
    async def test_authenticate_rejects_invalid_method(self, cloud_agent):
        """Test that authenticate rejects invalid method IDs."""
        with pytest.raises(RequestError) as exc_info:
            await cloud_agent.authenticate(method_id="invalid-method")

        assert exc_info.value.data is not None
        assert "Unsupported authentication method" in exc_info.value.data.get(
            "reason", ""
        )

    @pytest.mark.asyncio
    async def test_authenticate_executes_login_command(self, cloud_agent):
        """Test that authenticate executes the login_command for OAuth."""
        with patch(
            "openhands_cli.auth.login_command.login_command",
            new_callable=AsyncMock,
        ) as mock_login:
            result = await cloud_agent.authenticate(method_id="oauth")

            mock_login.assert_called_once_with(
                "https://app.all-hands.dev", skip_settings_sync=True
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_authenticate_handles_device_flow_error(self, cloud_agent):
        """Test that authenticate handles DeviceFlowError properly."""
        from openhands_cli.auth.device_flow import DeviceFlowError

        with patch(
            "openhands_cli.auth.login_command.login_command",
            new_callable=AsyncMock,
            side_effect=DeviceFlowError("User denied access"),
        ):
            with pytest.raises(RequestError) as exc_info:
                await cloud_agent.authenticate(method_id="oauth")

            assert exc_info.value.data is not None
            assert "Authentication failed" in exc_info.value.data.get("reason", "")


class TestPrompt:
    """Tests for the prompt method."""

    @pytest.mark.asyncio
    async def test_prompt_returns_end_turn_for_empty_prompt(
        self, cloud_agent, mock_connection
    ):
        """Test prompt returns end_turn for empty content."""
        session_id = str(uuid4())
        mock_workspace = MagicMock()
        mock_workspace.alive = True
        cloud_agent._active_workspaces[session_id] = mock_workspace

        with patch.object(
            cloud_agent, "_get_or_create_conversation", new_callable=AsyncMock
        ) as mock_get:
            mock_conversation = MagicMock()
            mock_get.return_value = mock_conversation

            response = await cloud_agent.prompt(prompt=[], session_id=session_id)

            assert response.stop_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_prompt_resumes_when_workspace_not_alive(
        self, cloud_agent, mock_connection
    ):
        """Test that prompt triggers resume when workspace is not alive."""
        session_id = str(uuid4())
        mock_workspace = MagicMock()
        mock_workspace.alive = False
        cloud_agent._active_workspaces[session_id] = mock_workspace

        with patch.object(
            cloud_agent, "_get_or_create_conversation", new_callable=AsyncMock
        ) as mock_get:
            mock_conversation = MagicMock()
            mock_get.return_value = mock_conversation

            await cloud_agent.prompt(prompt=[], session_id=session_id)

            # Verify _get_or_create_conversation was called with is_resuming=True
            mock_get.assert_called_once_with(session_id=session_id, is_resuming=True)

    @pytest.mark.asyncio
    async def test_prompt_does_not_resume_when_workspace_alive(
        self, cloud_agent, mock_connection
    ):
        """Test that prompt does not trigger resume when workspace is alive."""
        session_id = str(uuid4())
        mock_workspace = MagicMock()
        mock_workspace.alive = True
        cloud_agent._active_workspaces[session_id] = mock_workspace

        with patch.object(
            cloud_agent, "_get_or_create_conversation", new_callable=AsyncMock
        ) as mock_get:
            mock_conversation = MagicMock()
            mock_get.return_value = mock_conversation

            await cloud_agent.prompt(prompt=[], session_id=session_id)

            # Verify _get_or_create_conversation was called with is_resuming=False
            mock_get.assert_called_once_with(session_id=session_id, is_resuming=False)

    @pytest.mark.asyncio
    async def test_prompt_handles_exception(self, cloud_agent, mock_connection):
        """Test prompt handles exceptions and sends error message."""
        session_id = str(uuid4())
        mock_workspace = MagicMock()
        mock_workspace.alive = True
        cloud_agent._active_workspaces[session_id] = mock_workspace

        mock_conversation = MagicMock()
        mock_conversation.send_message.side_effect = Exception("Test error")

        with patch.object(
            cloud_agent, "_get_or_create_conversation", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_conversation

            with pytest.raises(RequestError) as exc_info:
                await cloud_agent.prompt(
                    prompt=[TextContentBlock(type="text", text="Hello")],
                    session_id=session_id,
                )

            assert exc_info.value.data is not None
            assert "Failed to process prompt" in exc_info.value.data.get("reason", "")
            mock_connection.session_update.assert_called()


class TestLoadSession:
    """Tests for the load_session method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invalid_session_id",
        ["not-a-uuid", "12345", "invalid-session"],
    )
    async def test_load_session_rejects_invalid_uuid(
        self, cloud_agent, invalid_session_id
    ):
        """Test load_session rejects invalid UUIDs."""
        with pytest.raises(RequestError) as exc_info:
            await cloud_agent.load_session(
                cwd="/tmp", mcp_servers=[], session_id=invalid_session_id
            )

        assert exc_info.value.data is not None
        assert "Invalid session ID" in exc_info.value.data.get("reason", "")

    @pytest.mark.asyncio
    async def test_load_session_not_found(self, cloud_agent):
        """Test load_session raises error when session not cached."""
        session_id = str(uuid4())

        with pytest.raises(RequestError) as exc_info:
            await cloud_agent.load_session(
                cwd="/tmp", mcp_servers=[], session_id=session_id
            )

        assert exc_info.value.data is not None
        assert "Session not found" in exc_info.value.data.get("reason", "")

    @pytest.mark.asyncio
    async def test_load_session_replays_historic_events(
        self, cloud_agent, mock_connection
    ):
        """Test that load_session replays historic events to the client."""
        from openhands.sdk import Message, TextContent
        from openhands.sdk.event.llm_convertible.message import MessageEvent

        session_id = str(uuid4())

        # Create mock events
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

        # Set up cached conversation with events
        mock_conversation = MagicMock()
        mock_conversation.state.events = [mock_event1, mock_event2]
        cloud_agent._active_sessions[session_id] = mock_conversation

        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.EventSubscriber"
        ) as mock_subscriber_class:
            mock_subscriber = AsyncMock()
            mock_subscriber_class.return_value = mock_subscriber

            response = await cloud_agent.load_session(
                cwd="/tmp", mcp_servers=[], session_id=session_id
            )

            # Verify response is returned
            assert response is not None
            assert response.modes is not None

            # Verify EventSubscriber was created
            mock_subscriber_class.assert_called_once_with(session_id, mock_connection)

            # Verify all historic events were replayed
            assert mock_subscriber.call_count == 2
            mock_subscriber.assert_any_call(mock_event1)
            mock_subscriber.assert_any_call(mock_event2)

    @pytest.mark.asyncio
    async def test_load_session_no_replay_when_no_events(
        self, cloud_agent, mock_connection
    ):
        """Test that load_session doesn't replay events when none exist."""
        session_id = str(uuid4())

        # Set up cached conversation with no events
        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        cloud_agent._active_sessions[session_id] = mock_conversation

        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.EventSubscriber"
        ) as mock_subscriber_class:
            mock_subscriber = AsyncMock()
            mock_subscriber_class.return_value = mock_subscriber

            response = await cloud_agent.load_session(
                cwd="/tmp", mcp_servers=[], session_id=session_id
            )

            # Verify response is returned
            assert response is not None

            # Verify EventSubscriber was NOT created (no events to replay)
            mock_subscriber_class.assert_not_called()


class TestCleanupSession:
    """Tests for the _cleanup_session method."""

    def test_cleanup_removes_workspace_and_conversation(self, cloud_agent):
        """Test _cleanup_session cleans up both workspace and conversation."""
        session_id = str(uuid4())
        mock_workspace = MagicMock()
        mock_conversation = MagicMock()
        cloud_agent._active_workspaces[session_id] = mock_workspace
        cloud_agent._active_sessions[session_id] = mock_conversation

        cloud_agent._cleanup_session(session_id)

        mock_workspace.cleanup.assert_called_once()
        mock_conversation.close.assert_called_once()
        assert session_id not in cloud_agent._active_workspaces
        assert session_id not in cloud_agent._active_sessions
