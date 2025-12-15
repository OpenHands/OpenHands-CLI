"""Unit tests for OAuth 2.0 Device Flow functionality."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from openhands_cli.auth.device_flow import (
    DeviceFlowClient,
    DeviceFlowError,
    authenticate_with_device_flow,
)


class TestDeviceFlowClient:
    """Test cases for DeviceFlowClient class."""

    def test_init(self):
        """Test DeviceFlowClient initialization."""
        server_url = "https://api.example.com"
        client = DeviceFlowClient(server_url)

        assert client.server_url == server_url

    @pytest.mark.asyncio
    async def test_start_device_flow_success(self):
        """Test successful device flow initiation."""
        client = DeviceFlowClient("https://api.example.com")

        mock_response = httpx.Response(status_code=200)
        mock_response._content = json.dumps(
            {
                "device_code": "device123",
                "user_code": "USER123",
                "verification_uri": "https://example.com/device",
                "interval": 5,
            }
        ).encode()

        with patch.object(client, "post") as mock_post:
            mock_post.return_value = mock_response

            result = await client.start_device_flow()

            assert result == ("device123", "USER123", "https://example.com/device", 5)
            mock_post.assert_called_once_with("/oauth/device/authorize", json_data={})

    @pytest.mark.asyncio
    async def test_start_device_flow_http_error(self):
        """Test device flow initiation with HTTP error."""
        client = DeviceFlowClient("https://api.example.com")

        with patch.object(client, "post") as mock_post:
            from openhands_cli.auth.http_client import AuthHttpError

            mock_post.side_effect = AuthHttpError("Network error")

            with pytest.raises(
                DeviceFlowError, match="Failed to start device flow: Network error"
            ):
                await client.start_device_flow()

    @pytest.mark.asyncio
    async def test_start_device_flow_missing_fields(self):
        """Test device flow initiation with missing response fields."""
        client = DeviceFlowClient("https://api.example.com")

        mock_response = httpx.Response(status_code=200)
        mock_response._content = json.dumps(
            {
                "device_code": "device123",
                # Missing user_code, verification_uri, interval
            }
        ).encode()

        with patch.object(client, "post") as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(DeviceFlowError, match="Failed to start device flow"):
                await client.start_device_flow()

    @pytest.mark.asyncio
    async def test_poll_for_token_success(self):
        """Test successful token polling."""
        client = DeviceFlowClient("https://api.example.com")

        # Mock successful response
        success_response = httpx.Response(status_code=200)
        success_response._content = json.dumps(
            {"access_token": "token123", "token_type": "Bearer"}
        ).encode()

        with patch.object(client, "post") as mock_post:
            mock_post.return_value = success_response

            result = await client.poll_for_token("device123", 1)

            assert result == {"access_token": "token123", "token_type": "Bearer"}
            mock_post.assert_called_once_with(
                "/oauth/device/token",
                form_data={"device_code": "device123"},
                raise_for_status=False,
            )

    @pytest.mark.asyncio
    async def test_poll_for_token_authorization_pending(self):
        """Test token polling with authorization pending."""
        client = DeviceFlowClient("https://api.example.com")

        # Mock pending response followed by success
        pending_response = httpx.Response(status_code=400)
        pending_response._content = json.dumps(
            {
                "error": "authorization_pending",
                "error_description": "User hasn't authorized yet",
            }
        ).encode()

        success_response = httpx.Response(status_code=200)
        success_response._content = json.dumps(
            {"access_token": "token123", "token_type": "Bearer"}
        ).encode()

        with patch.object(client, "post") as mock_post:
            mock_post.side_effect = [pending_response, success_response]

            with patch("asyncio.sleep") as mock_sleep:
                result = await client.poll_for_token("device123", 1)

                assert result == {"access_token": "token123", "token_type": "Bearer"}
                mock_sleep.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_poll_for_token_slow_down(self):
        """Test token polling with slow down request."""
        client = DeviceFlowClient("https://api.example.com")

        # Mock slow down response followed by success
        slow_down_response = httpx.Response(status_code=400)
        slow_down_response._content = json.dumps(
            {"error": "slow_down", "error_description": "Polling too frequently"}
        ).encode()

        success_response = httpx.Response(status_code=200)
        success_response._content = json.dumps(
            {"access_token": "token123", "token_type": "Bearer"}
        ).encode()

        with patch.object(client, "post") as mock_post:
            mock_post.side_effect = [slow_down_response, success_response]

            with patch("asyncio.sleep") as mock_sleep:
                result = await client.poll_for_token("device123", 5)

                assert result == {"access_token": "token123", "token_type": "Bearer"}
                # Should double the interval (5 * 2 = 10)
                mock_sleep.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_poll_for_token_expired_token(self):
        """Test token polling with expired token error."""
        client = DeviceFlowClient("https://api.example.com")

        expired_response = httpx.Response(status_code=400)
        expired_response._content = json.dumps(
            {"error": "expired_token", "error_description": "Device code has expired"}
        ).encode()

        with patch.object(client, "post") as mock_post:
            mock_post.return_value = expired_response

            with pytest.raises(DeviceFlowError, match="Device code has expired"):
                await client.poll_for_token("device123", 1)

    @pytest.mark.asyncio
    async def test_poll_for_token_access_denied(self):
        """Test token polling with access denied error."""
        client = DeviceFlowClient("https://api.example.com")

        denied_response = httpx.Response(status_code=400)
        denied_response._content = json.dumps(
            {"error": "access_denied", "error_description": "User denied the request"}
        ).encode()

        with patch.object(client, "post") as mock_post:
            mock_post.return_value = denied_response

            with pytest.raises(
                DeviceFlowError, match="User denied the authorization request"
            ):
                await client.poll_for_token("device123", 1)

    @pytest.mark.asyncio
    async def test_poll_for_token_unknown_error(self):
        """Test token polling with unknown error."""
        client = DeviceFlowClient("https://api.example.com")

        error_response = httpx.Response(status_code=400)
        error_response._content = json.dumps(
            {"error": "unknown_error", "error_description": "Something went wrong"}
        ).encode()

        with patch.object(client, "post") as mock_post:
            mock_post.return_value = error_response

            with pytest.raises(
                DeviceFlowError,
                match="Authorization error: unknown_error - Something went wrong",
            ):
                await client.poll_for_token("device123", 1)

    @pytest.mark.asyncio
    async def test_poll_for_token_network_error(self):
        """Test token polling with network error."""
        client = DeviceFlowClient("https://api.example.com")

        with patch.object(client, "post") as mock_post:
            from openhands_cli.auth.http_client import AuthHttpError

            mock_post.side_effect = AuthHttpError("Connection failed")

            with pytest.raises(
                DeviceFlowError, match="Network error during token polling"
            ):
                await client.poll_for_token("device123", 1)

    @pytest.mark.asyncio
    async def test_poll_for_token_invalid_json_response(self):
        """Test token polling with invalid JSON response."""
        client = DeviceFlowClient("https://api.example.com")

        invalid_response = httpx.Response(status_code=500)
        invalid_response._content = b"Internal Server Error"

        with patch.object(client, "post") as mock_post:
            mock_post.return_value = invalid_response

            with pytest.raises(
                DeviceFlowError, match="Unexpected response from server: 500"
            ):
                await client.poll_for_token("device123", 1)

    @pytest.mark.asyncio
    async def test_poll_for_token_timeout(self):
        """Test token polling timeout."""
        client = DeviceFlowClient("https://api.example.com")

        # Mock pending response that never succeeds
        pending_response = httpx.Response(status_code=400)
        pending_response._content = json.dumps(
            {"error": "authorization_pending"}
        ).encode()

        with patch.object(client, "post") as mock_post:
            mock_post.return_value = pending_response

            with patch("asyncio.sleep"):
                with pytest.raises(
                    DeviceFlowError, match="Timeout waiting for user authorization"
                ):
                    # Use a very short timeout to make the test fast
                    await client.poll_for_token("device123", 1, timeout=0.1)

    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        """Test complete authentication flow success."""
        client = DeviceFlowClient("https://api.example.com")

        with patch.object(client, "start_device_flow") as mock_start:
            mock_start.return_value = (
                "device123",
                "USER123",
                "https://example.com/device",
                5,
            )

            with patch.object(client, "poll_for_token") as mock_poll:
                mock_poll.return_value = {
                    "access_token": "token123",
                    "token_type": "Bearer",
                }

                with patch("openhands_cli.auth.device_flow._p") as mock_print:
                    with patch("webbrowser.open") as mock_browser:
                        result = await client.authenticate()

                        assert result == {
                            "access_token": "token123",
                            "token_type": "Bearer",
                        }

                        # Verify print calls for user instructions
                        assert mock_print.call_count >= 5  # Multiple print statements
                        mock_poll.assert_called_once_with("device123", 5)

                        # Verify browser was opened with correct URL
                        mock_browser.assert_called_once_with(
                            "https://example.com/device?user_code=USER123"
                        )

    @pytest.mark.asyncio
    async def test_authenticate_browser_open_failure(self):
        """Test authentication when browser fails to open."""
        client = DeviceFlowClient("https://api.example.com")

        with patch.object(client, "start_device_flow") as mock_start:
            mock_start.return_value = (
                "device123",
                "USER123",
                "https://example.com/device",
                5,
            )

            with patch.object(client, "poll_for_token") as mock_poll:
                mock_poll.return_value = {
                    "access_token": "token123",
                    "token_type": "Bearer",
                }

                with patch("openhands_cli.auth.device_flow._p"):
                    with patch("webbrowser.open") as mock_browser:
                        mock_browser.side_effect = Exception("Browser not available")

                        result = await client.authenticate()

                        assert result == {
                            "access_token": "token123",
                            "token_type": "Bearer",
                        }

                        # Verify browser open was attempted
                        mock_browser.assert_called_once_with(
                            "https://example.com/device?user_code=USER123"
                        )

                        # Should still complete successfully even if browser fails
                        mock_poll.assert_called_once_with("device123", 5)

    @pytest.mark.asyncio
    async def test_authenticate_start_flow_error(self):
        """Test authentication with start flow error."""
        client = DeviceFlowClient("https://api.example.com")

        with patch.object(client, "start_device_flow") as mock_start:
            mock_start.side_effect = DeviceFlowError("Failed to start")

            with patch("openhands_cli.auth.device_flow._p"):
                with pytest.raises(DeviceFlowError, match="Failed to start"):
                    await client.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_poll_error(self):
        """Test authentication with polling error."""
        client = DeviceFlowClient("https://api.example.com")

        with patch.object(client, "start_device_flow") as mock_start:
            mock_start.return_value = (
                "device123",
                "USER123",
                "https://example.com/device",
                5,
            )

            with patch.object(client, "poll_for_token") as mock_poll:
                mock_poll.side_effect = DeviceFlowError("Polling failed")

                with patch("openhands_cli.auth.device_flow._p"):
                    with pytest.raises(DeviceFlowError, match="Polling failed"):
                        await client.authenticate()


@pytest.mark.asyncio
async def test_authenticate_with_device_flow():
    """Test convenience function for device flow authentication."""
    server_url = "https://api.example.com"
    expected_tokens = {"access_token": "token123", "token_type": "Bearer"}

    with patch("openhands_cli.auth.device_flow.DeviceFlowClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.authenticate.return_value = expected_tokens

        result = await authenticate_with_device_flow(server_url)

        assert result == expected_tokens
        mock_client_class.assert_called_once_with(server_url)
        mock_client.authenticate.assert_called_once()
