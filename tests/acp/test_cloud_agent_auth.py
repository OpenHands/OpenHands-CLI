"""Tests for OpenHandsCloudACPAgent authentication."""

from unittest.mock import AsyncMock, MagicMock, patch

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
    return OpenHandsCloudACPAgent(
        conn=mock_connection,
        cloud_api_key="test-api-key",
        initial_confirmation_mode="always-ask",
        cloud_api_url="https://app.all-hands.dev",
    )


@pytest.mark.asyncio
async def test_new_session_requires_authentication(cloud_agent):
    """Test that new_session raises auth_required when user is not authenticated."""
    # Mock TokenStorage to indicate no API key stored
    with patch(
        "openhands_cli.acp_impl.agent.remote_agent.TokenStorage"
    ) as mock_storage_class:
        mock_storage = MagicMock()
        mock_storage.has_api_key.return_value = False
        mock_storage_class.return_value = mock_storage

        # Should raise auth_required error
        with pytest.raises(RequestError) as exc_info:
            await cloud_agent.new_session(cwd="/tmp", mcp_servers=[])

        # Verify the error is auth_required type
        error = exc_info.value
        assert error.code == -32601 or "auth" in str(error).lower()


@pytest.mark.asyncio
async def test_new_session_succeeds_when_authenticated(cloud_agent):
    """Test that new_session proceeds when user is authenticated."""
    with (
        patch(
            "openhands_cli.acp_impl.agent.remote_agent.TokenStorage"
        ) as mock_storage_class,
        patch.object(
            cloud_agent._shared_handler, "new_session", new_callable=AsyncMock
        ) as mock_new_session,
    ):
        # Mock TokenStorage to indicate API key is stored
        mock_storage = MagicMock()
        mock_storage.has_api_key.return_value = True
        mock_storage.get_api_key.return_value = "valid-api-key"
        mock_storage_class.return_value = mock_storage

        # Mock the shared handler's new_session
        mock_response = MagicMock()
        mock_new_session.return_value = mock_response

        # Should not raise, should call shared handler
        result = await cloud_agent.new_session(cwd="/tmp", mcp_servers=[])

        mock_new_session.assert_called_once()
        assert result == mock_response


@pytest.mark.asyncio
async def test_authenticate_method_validation(cloud_agent):
    """Test that authenticate rejects invalid method IDs."""
    with pytest.raises(RequestError) as exc_info:
        await cloud_agent.authenticate(method_id="invalid-method")

    error = exc_info.value
    # The error data contains the reason
    assert error.data is not None
    assert "Unsupported authentication method" in error.data.get("reason", "")


@pytest.mark.asyncio
async def test_authenticate_with_oauth_success(cloud_agent):
    """Test successful OAuth authentication."""
    with (
        patch(
            "openhands_cli.auth.device_flow.authenticate_with_device_flow",
            new_callable=AsyncMock,
        ) as mock_auth,
        patch(
            "openhands_cli.acp_impl.agent.remote_agent.TokenStorage"
        ) as mock_storage_class,
        patch(
            "openhands_cli.auth.api_client.fetch_user_data_after_oauth",
            new_callable=AsyncMock,
        ) as mock_fetch,
    ):
        # Mock successful OAuth flow
        mock_auth.return_value = {"access_token": "new-api-key"}

        # Mock token storage
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock user data fetch
        mock_fetch.return_value = {"user": "test"}

        result = await cloud_agent.authenticate(method_id="oauth")

        # Verify OAuth flow was called
        mock_auth.assert_called_once_with("https://app.all-hands.dev")

        # Verify token was stored
        mock_storage.store_api_key.assert_called_once_with("new-api-key")

        # Verify agent's API key was updated
        assert cloud_agent._cloud_api_key == "new-api-key"

        # Verify response
        assert result is not None


@pytest.mark.asyncio
async def test_authenticate_handles_device_flow_error(cloud_agent):
    """Test that authenticate handles DeviceFlowError properly."""
    with patch(
        "openhands_cli.auth.device_flow.authenticate_with_device_flow",
        new_callable=AsyncMock,
    ) as mock_auth:
        from openhands_cli.auth.device_flow import DeviceFlowError

        mock_auth.side_effect = DeviceFlowError("User denied access")

        with pytest.raises(RequestError) as exc_info:
            await cloud_agent.authenticate(method_id="oauth")

        error = exc_info.value
        # The error data contains the reason
        assert error.data is not None
        assert "Authentication failed" in error.data.get("reason", "")


@pytest.mark.asyncio
async def test_authenticate_continues_on_user_data_fetch_error(cloud_agent):
    """Test that authenticate succeeds even if user data fetch fails."""
    with (
        patch(
            "openhands_cli.auth.device_flow.authenticate_with_device_flow",
            new_callable=AsyncMock,
        ) as mock_auth,
        patch(
            "openhands_cli.acp_impl.agent.remote_agent.TokenStorage"
        ) as mock_storage_class,
        patch(
            "openhands_cli.auth.api_client.fetch_user_data_after_oauth",
            new_callable=AsyncMock,
        ) as mock_fetch,
    ):
        from openhands_cli.auth.api_client import ApiClientError

        # Mock successful OAuth flow
        mock_auth.return_value = {"access_token": "new-api-key"}

        # Mock token storage
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock user data fetch to fail
        mock_fetch.side_effect = ApiClientError("Failed to fetch data")

        # Should still succeed
        result = await cloud_agent.authenticate(method_id="oauth")

        # Verify OAuth flow was called
        mock_auth.assert_called_once()

        # Verify token was still stored
        mock_storage.store_api_key.assert_called_once_with("new-api-key")

        # Verify response is still returned
        assert result is not None


@pytest.mark.asyncio
async def test_is_authenticated_returns_false_when_no_key():
    """Test _is_authenticated returns False when no API key is stored."""
    mock_conn = AsyncMock()
    agent = OpenHandsCloudACPAgent(
        conn=mock_conn,
        cloud_api_key="",
        initial_confirmation_mode="always-ask",
    )

    with patch(
        "openhands_cli.acp_impl.agent.remote_agent.TokenStorage"
    ) as mock_storage_class:
        mock_storage = MagicMock()
        mock_storage.has_api_key.return_value = False
        mock_storage_class.return_value = mock_storage

        assert agent._is_authenticated() is False


@pytest.mark.asyncio
async def test_is_authenticated_returns_true_when_key_exists():
    """Test _is_authenticated returns True when API key is stored."""
    mock_conn = AsyncMock()
    agent = OpenHandsCloudACPAgent(
        conn=mock_conn,
        cloud_api_key="test-key",
        initial_confirmation_mode="always-ask",
    )

    with patch(
        "openhands_cli.acp_impl.agent.remote_agent.TokenStorage"
    ) as mock_storage_class:
        mock_storage = MagicMock()
        mock_storage.has_api_key.return_value = True
        mock_storage.get_api_key.return_value = "valid-key"
        mock_storage_class.return_value = mock_storage

        assert agent._is_authenticated() is True
