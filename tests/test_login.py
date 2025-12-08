"""Tests for OpenHands Cloud login functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands_cli.user_actions.login_action import (
    DeviceAuthError,
    DeviceAuthTimeoutError,
    login_to_openhands_cloud,
    poll_for_token,
    request_device_code,
)


@pytest.mark.asyncio
async def test_request_device_code_success():
    """Test successful device code request."""
    mock_response = {
        "device_code": "test_device_code_123",
        "user_code": "ABCD-1234",
        "verification_uri": "https://app.all-hands.dev/device",
        "expires_in": 300,
        "interval": 5,
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp

        result = await request_device_code("https://test.example.com")

        assert result == mock_response
        mock_client.post.assert_called_once_with(
            "https://test.example.com/api/v1/auth/device",
            timeout=10.0,
        )


@pytest.mark.asyncio
async def test_request_device_code_http_error():
    """Test device code request with HTTP error."""
    import httpx

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Raise httpx.HTTPError instead of generic Exception
        mock_client.post.side_effect = httpx.HTTPError("Network error")

        with pytest.raises(DeviceAuthError, match="Failed to request device code"):
            await request_device_code("https://test.example.com")


@pytest.mark.asyncio
async def test_poll_for_token_success():
    """Test successful token polling."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # First call returns pending, second returns the API key
        pending_resp = MagicMock()
        pending_resp.status_code = 200
        pending_resp.json.return_value = {"status": "pending"}

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {"api_key": "ohsk_test_key_123"}

        mock_client.post.side_effect = [pending_resp, success_resp]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await poll_for_token(
                device_code="test_code",
                interval=1,
                expires_in=300,
                base_url="https://test.example.com",
            )

        assert result == "ohsk_test_key_123"
        assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_poll_for_token_timeout():
    """Test token polling timeout."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Always return pending
        pending_resp = MagicMock()
        pending_resp.status_code = 200
        pending_resp.json.return_value = {"status": "pending"}
        mock_client.post.return_value = pending_resp

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("time.time") as mock_time:
                # Simulate time passing beyond expiration
                mock_time.side_effect = [0, 301]  # Start at 0, then 301 seconds later

                with pytest.raises(
                    DeviceAuthTimeoutError, match="Device authorization timed out"
                ):
                    await poll_for_token(
                        device_code="test_code",
                        interval=1,
                        expires_in=300,
                        base_url="https://test.example.com",
                    )


@pytest.mark.asyncio
async def test_poll_for_token_expired():
    """Test token polling with expired token error."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        error_resp = MagicMock()
        error_resp.status_code = 400
        error_resp.json.return_value = {"error": "expired_token"}
        mock_client.post.return_value = error_resp

        with pytest.raises(DeviceAuthTimeoutError, match="Device code expired"):
            await poll_for_token(
                device_code="test_code",
                interval=1,
                expires_in=300,
                base_url="https://test.example.com",
            )


@pytest.mark.asyncio
async def test_poll_for_token_access_denied():
    """Test token polling with access denied error."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        error_resp = MagicMock()
        error_resp.status_code = 400
        error_resp.json.return_value = {"error": "access_denied"}
        mock_client.post.return_value = error_resp

        with pytest.raises(DeviceAuthError, match="Authorization was denied"):
            await poll_for_token(
                device_code="test_code",
                interval=1,
                expires_in=300,
                base_url="https://test.example.com",
            )


@pytest.mark.asyncio
async def test_login_to_openhands_cloud_success(capsys):
    """Test successful login flow."""
    device_data = {
        "device_code": "test_device_code",
        "user_code": "ABCD-1234",
        "verification_uri": "https://app.all-hands.dev/device",
        "expires_in": 300,
        "interval": 5,
    }

    with patch(
        "openhands_cli.user_actions.login_action.request_device_code",
        new_callable=AsyncMock,
    ) as mock_request:
        with patch(
            "openhands_cli.user_actions.login_action.poll_for_token",
            new_callable=AsyncMock,
        ) as mock_poll:
            with patch("webbrowser.open") as mock_browser:
                with patch(
                    "openhands_cli.user_actions.login_action.AgentStore"
                ) as mock_store_class:
                    mock_request.return_value = device_data
                    mock_poll.return_value = "ohsk_test_key_123"

                    # Mock the store
                    mock_store = MagicMock()
                    mock_settings = MagicMock()
                    mock_settings.llm = MagicMock()
                    mock_store.load.return_value = mock_settings
                    mock_store.settings_file = "/tmp/test_settings.json"
                    mock_store_class.return_value = mock_store

                    result = await login_to_openhands_cloud("https://test.example.com")

                    assert result == "ohsk_test_key_123"

                    # Verify browser was opened
                    mock_browser.assert_called_once_with(
                        "https://app.all-hands.dev/device"
                    )

                    # Verify settings were saved
                    mock_store.save.assert_called_once()
                    assert mock_settings.llm.api_key == "ohsk_test_key_123"  # noqa: E712

                    # Check output
                    captured = capsys.readouterr()
                    assert "OpenHands Cloud Login" in captured.out
                    assert "ABCD-1234" in captured.out
                    assert "Authentication successful" in captured.out


@pytest.mark.asyncio
async def test_login_to_openhands_cloud_device_error(capsys):
    """Test login flow with device code request error."""
    with patch(
        "openhands_cli.user_actions.login_action.request_device_code",
        new_callable=AsyncMock,
    ) as mock_request:
        mock_request.side_effect = DeviceAuthError("Network error")

        with pytest.raises(DeviceAuthError):
            await login_to_openhands_cloud("https://test.example.com")

        captured = capsys.readouterr()
        assert "Error: Network error" in captured.out


@pytest.mark.asyncio
async def test_login_to_openhands_cloud_browser_error(capsys):
    """Test login flow when browser fails to open."""
    device_data = {
        "device_code": "test_device_code",
        "user_code": "ABCD-1234",
        "verification_uri": "https://app.all-hands.dev/device",
        "expires_in": 300,
        "interval": 5,
    }

    with patch(
        "openhands_cli.user_actions.login_action.request_device_code",
        new_callable=AsyncMock,
    ) as mock_request:
        with patch(
            "openhands_cli.user_actions.login_action.poll_for_token",
            new_callable=AsyncMock,
        ) as mock_poll:
            with patch("webbrowser.open") as mock_browser:
                with patch(
                    "openhands_cli.user_actions.login_action.AgentStore"
                ) as mock_store_class:
                    mock_request.return_value = device_data
                    mock_poll.return_value = "ohsk_test_key_123"
                    mock_browser.side_effect = Exception("Browser not found")

                    mock_store = MagicMock()
                    mock_settings = MagicMock()
                    mock_settings.llm = MagicMock()
                    mock_store.load.return_value = mock_settings
                    mock_store.settings_file = "/tmp/test_settings.json"
                    mock_store_class.return_value = mock_store

                    result = await login_to_openhands_cloud("https://test.example.com")

                    assert result == "ohsk_test_key_123"

                    # Check that it showed manual instruction
                    captured = capsys.readouterr()
                    assert "Could not open browser automatically" in captured.out
                    assert "Please manually open" in captured.out
