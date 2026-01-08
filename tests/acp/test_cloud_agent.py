"""Tests for OpenHandsCloudACPAgent."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from acp import RequestError

from openhands_cli.acp_impl.agent import OpenHandsCloudACPAgent


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    conn = AsyncMock()
    return conn


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


class TestCloudAgentInit:
    """Tests for agent initialization."""

    @pytest.mark.parametrize(
        "confirmation_mode",
        ["always-ask", "always-approve", "llm-approve"],
    )
    def test_init_with_confirmation_modes(self, mock_connection, confirmation_mode):
        """Test agent can be initialized with any valid confirmation mode."""
        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.TokenStorage"
        ) as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.get_api_key.return_value = "test-api-key"
            mock_storage_class.return_value = mock_storage

            agent = OpenHandsCloudACPAgent(
                conn=mock_connection,
                initial_confirmation_mode=confirmation_mode,
            )

            assert agent._initial_confirmation_mode == confirmation_mode

    def test_init_with_resume_id(self, mock_connection):
        """Test agent stores resume conversation ID."""
        resume_id = str(uuid4())
        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.TokenStorage"
        ) as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.get_api_key.return_value = "test-api-key"
            mock_storage_class.return_value = mock_storage

            agent = OpenHandsCloudACPAgent(
                conn=mock_connection,
                initial_confirmation_mode="always-ask",
                resume_conversation_id=resume_id,
            )

            assert agent._resume_conversation_id == resume_id


class TestVerifyAndGetSandboxId:
    """Tests for the _verify_and_get_sandbox_id method."""

    @pytest.mark.asyncio
    async def test_verify_requires_api_key(self, mock_connection):
        """Test _verify_and_get_sandbox_id raises auth_required without API key."""
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
                await agent._verify_and_get_sandbox_id("test-conversation-id")

            assert "Authentication required" in str(exc_info.value.data)

    @pytest.mark.asyncio
    async def test_verify_handles_not_found(self, cloud_agent):
        """Test _verify_and_get_sandbox_id handles 404 errors."""
        from openhands_cli.auth.api_client import ApiClientError

        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.OpenHandsApiClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_conversation_info.side_effect = ApiClientError("HTTP 404")
            mock_client_class.return_value = mock_client

            with pytest.raises(RequestError) as exc_info:
                await cloud_agent._verify_and_get_sandbox_id("test-conversation-id")

            assert "Conversation not found" in exc_info.value.data.get("reason", "")

    @pytest.mark.asyncio
    async def test_verify_handles_no_sandbox(self, cloud_agent):
        """Test _verify_and_get_sandbox_id handles conversations without sandbox."""
        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.OpenHandsApiClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_conversation_info.return_value = {
                "id": "test",
                "sandbox_id": None,
            }
            mock_client_class.return_value = mock_client

            with pytest.raises(RequestError) as exc_info:
                await cloud_agent._verify_and_get_sandbox_id("test-conversation-id")

            assert "no associated sandbox" in exc_info.value.data.get("reason", "")

    @pytest.mark.asyncio
    async def test_verify_returns_sandbox_id(self, cloud_agent):
        """Test _verify_and_get_sandbox_id returns sandbox_id on success."""
        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.OpenHandsApiClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_conversation_info.return_value = {
                "id": "test",
                "sandbox_id": "sandbox-123",
            }
            mock_client_class.return_value = mock_client

            sandbox_id = await cloud_agent._verify_and_get_sandbox_id(
                "test-conversation-id"
            )

            assert sandbox_id == "sandbox-123"


class TestGetOrCreateConversation:
    """Tests for the _get_or_create_conversation method."""

    @pytest.mark.asyncio
    async def test_returns_cached_conversation(self, cloud_agent):
        """Test _get_or_create_conversation returns cached conversation."""
        session_id = str(uuid4())
        mock_conversation = MagicMock()
        cloud_agent._active_sessions[session_id] = mock_conversation

        result = await cloud_agent._get_or_create_conversation(session_id)

        assert result == mock_conversation

    @pytest.mark.asyncio
    async def test_creates_new_conversation(self, cloud_agent):
        """Test _get_or_create_conversation creates new conversation when not cached."""
        session_id = str(uuid4())

        with patch.object(cloud_agent, "_setup_cloud_conversation") as mock_setup:
            mock_conversation = MagicMock()
            mock_workspace = MagicMock()
            mock_setup.return_value = (mock_conversation, mock_workspace)

            result = await cloud_agent._get_or_create_conversation(
                session_id, mcp_servers={}
            )

            assert result == mock_conversation
            assert session_id in cloud_agent._active_sessions
            assert session_id in cloud_agent._active_workspaces

    @pytest.mark.asyncio
    async def test_verifies_sandbox_when_resuming(self, cloud_agent):
        """Test _get_or_create_conversation verifies sandbox when resuming."""
        session_id = str(uuid4())

        with (
            patch.object(
                cloud_agent, "_verify_and_get_sandbox_id", new_callable=AsyncMock
            ) as mock_verify,
            patch.object(cloud_agent, "_setup_cloud_conversation") as mock_setup,
        ):
            mock_verify.return_value = "sandbox-123"
            mock_conversation = MagicMock()
            mock_workspace = MagicMock()
            mock_setup.return_value = (mock_conversation, mock_workspace)

            await cloud_agent._get_or_create_conversation(session_id, is_resuming=True)

            mock_verify.assert_called_once_with(session_id)
            mock_setup.assert_called_once()
            # Verify sandbox_id was passed to setup
            assert mock_setup.call_args[1].get("sandbox_id") == "sandbox-123"


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

        assert "Invalid session ID" in exc_info.value.data.get("reason", "")

    @pytest.mark.asyncio
    async def test_load_session_returns_cached(self, cloud_agent, mock_connection):
        """Test load_session returns cached session and streams history."""
        session_id = str(uuid4())
        mock_event = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.state.events = [mock_event]
        cloud_agent._active_sessions[session_id] = mock_conversation

        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.EventSubscriber"
        ) as mock_subscriber_class:
            mock_subscriber = AsyncMock()
            mock_subscriber_class.return_value = mock_subscriber

            response = await cloud_agent.load_session(
                cwd="/tmp", mcp_servers=[], session_id=session_id
            )

            assert response is not None
            assert response.modes is not None
            mock_subscriber.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_load_session_not_found(self, cloud_agent):
        """Test load_session raises error when session not cached."""
        session_id = str(uuid4())

        with pytest.raises(RequestError) as exc_info:
            await cloud_agent.load_session(
                cwd="/tmp", mcp_servers=[], session_id=session_id
            )

        assert "Session not found" in exc_info.value.data.get("reason", "")


class TestPrompt:
    """Tests for the prompt method."""

    @pytest.mark.asyncio
    async def test_prompt_returns_end_turn_for_empty_prompt(self, cloud_agent):
        """Test prompt returns end_turn for empty content."""
        session_id = str(uuid4())

        with patch.object(
            cloud_agent, "_get_or_create_conversation", new_callable=AsyncMock
        ) as mock_get:
            mock_conversation = MagicMock()
            mock_get.return_value = mock_conversation

            # Empty prompt list
            response = await cloud_agent.prompt(prompt=[], session_id=session_id)

            assert response.stop_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_prompt_handles_exception(self, cloud_agent, mock_connection):
        """Test prompt handles exceptions and sends error message."""
        from acp.schema import TextContentBlock

        session_id = str(uuid4())
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

            assert "Failed to process prompt" in exc_info.value.data.get("reason", "")
            # Verify error message was sent
            mock_connection.session_update.assert_called()


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

    def test_cleanup_handles_missing_session(self, cloud_agent):
        """Test _cleanup_session handles non-existent sessions gracefully."""
        session_id = str(uuid4())
        # Should not raise
        cloud_agent._cleanup_session(session_id)


class TestCancel:
    """Tests for the cancel method."""

    @pytest.mark.asyncio
    async def test_cancel_delegates_to_shared_handler(self, cloud_agent):
        """Test cancel delegates to shared handler."""
        session_id = str(uuid4())

        with patch.object(
            cloud_agent._shared_handler, "cancel", new_callable=AsyncMock
        ) as mock_cancel:
            await cloud_agent.cancel(session_id=session_id)

            mock_cancel.assert_called_once_with(cloud_agent, session_id)


class TestDelegatedMethods:
    """Tests for methods that delegate to shared handler."""

    @pytest.mark.asyncio
    async def test_initialize_delegates(self, cloud_agent):
        """Test initialize delegates to shared handler."""
        with patch.object(
            cloud_agent._shared_handler, "initialize", new_callable=AsyncMock
        ) as mock_init:
            await cloud_agent.initialize(protocol_version=1)
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_session_mode_delegates(self, cloud_agent):
        """Test set_session_mode delegates to shared handler."""
        with patch.object(
            cloud_agent._shared_handler, "set_session_mode", new_callable=AsyncMock
        ) as mock_set:
            await cloud_agent.set_session_mode(
                mode_id="always-ask", session_id="test-session"
            )
            mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_sessions_delegates(self, cloud_agent):
        """Test list_sessions delegates to shared handler."""
        with patch.object(
            cloud_agent._shared_handler, "list_sessions", new_callable=AsyncMock
        ) as mock_list:
            await cloud_agent.list_sessions()
            mock_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_session_model_delegates(self, cloud_agent):
        """Test set_session_model delegates to shared handler."""
        with patch.object(
            cloud_agent._shared_handler, "set_session_model", new_callable=AsyncMock
        ) as mock_set:
            await cloud_agent.set_session_model(
                model_id="test-model", session_id="test-session"
            )
            mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_ext_method_delegates(self, cloud_agent):
        """Test ext_method delegates to shared handler."""
        with patch.object(
            cloud_agent._shared_handler, "ext_method", new_callable=AsyncMock
        ) as mock_ext:
            await cloud_agent.ext_method("test", {})
            mock_ext.assert_called_once()

    @pytest.mark.asyncio
    async def test_ext_notification_delegates(self, cloud_agent):
        """Test ext_notification delegates to shared handler."""
        with patch.object(
            cloud_agent._shared_handler, "ext_notification", new_callable=AsyncMock
        ) as mock_ext:
            await cloud_agent.ext_notification("test", {})
            mock_ext.assert_called_once()
