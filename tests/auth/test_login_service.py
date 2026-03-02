"""Unit tests for login service functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands_cli.auth.device_flow import (
    DeviceAuthorizationResponse,
    DeviceTokenResponse,
)
from openhands_cli.auth.login_service import (
    NullLoginCallback,
    StatusType,
    run_login_flow,
)


class MockLoginCallback:
    """Mock implementation of LoginProgressCallback for testing."""

    def __init__(self):
        self.status_messages = []
        self.status_types = []
        self.verification_urls = []
        self.instructions = []

    def on_status(
        self, message: str, status_type: StatusType = StatusType.INFO
    ) -> None:
        self.status_messages.append(message)
        self.status_types.append(status_type)

    def on_verification_url(self, url: str, user_code: str) -> None:
        self.verification_urls.append((url, user_code))

    def on_instructions(
        self, message: str, status_type: StatusType = StatusType.INFO
    ) -> None:
        self.instructions.append(message)


class TestNullLoginCallback:
    """Test NullLoginCallback does nothing (no errors)."""

    def test_all_methods_are_no_ops(self):
        """Test that all callback methods run without errors."""
        callback = NullLoginCallback()
        callback.on_status("test")
        callback.on_status("test with type", StatusType.SUCCESS)
        callback.on_verification_url("url", "code")
        callback.on_instructions("test")
        callback.on_instructions("test with type", StatusType.SUCCESS)


class TestRunLoginFlow:
    """Test cases for run_login_flow."""

    @pytest.mark.asyncio
    async def test_already_logged_in_with_valid_token(self):
        """Test flow when user already has a valid token."""
        callback = MockLoginCallback()

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.utils.is_token_valid") as mock_is_valid:
                with patch(
                    "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                ) as mock_fetch:
                    mock_storage = MagicMock()
                    mock_storage_class.return_value = mock_storage
                    mock_storage.get_api_key.return_value = "existing-token"
                    mock_is_valid.return_value = True
                    mock_fetch.return_value = None

                    result = await run_login_flow(
                        server_url="https://example.com",
                        callback=callback,
                    )

                    assert result is True
                    assert any(
                        "Already logged in" in msg for msg in callback.status_messages
                    )
                    # Settings sync success is communicated via instructions
                    assert any(
                        "Settings synchronized" in msg for msg in callback.instructions
                    )

    @pytest.mark.asyncio
    async def test_already_logged_in_skip_settings_sync(self):
        """Test flow when user is logged in and settings sync is skipped."""
        callback = MockLoginCallback()

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.utils.is_token_valid") as mock_is_valid:
                with patch(
                    "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                ) as mock_fetch:
                    mock_storage = MagicMock()
                    mock_storage_class.return_value = mock_storage
                    mock_storage.get_api_key.return_value = "existing-token"
                    mock_is_valid.return_value = True

                    result = await run_login_flow(
                        server_url="https://example.com",
                        callback=callback,
                        skip_settings_sync=True,
                    )

                    assert result is True
                    mock_fetch.assert_not_called()
                    # No sync instructions when skipped
                    assert not any(
                        "Settings synchronized" in msg for msg in callback.instructions
                    )

    @pytest.mark.asyncio
    async def test_expired_token_triggers_logout(self):
        """Test that expired token triggers logout before new login."""
        callback = MockLoginCallback()

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.utils.is_token_valid") as mock_is_valid:
                with patch(
                    "openhands_cli.auth.logout_command.logout_command"
                ) as mock_logout:
                    with patch(
                        "openhands_cli.auth.device_flow.DeviceFlowClient"
                    ) as mock_client_class:
                        with patch(
                            "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                        ):
                            mock_storage = MagicMock()
                            mock_storage_class.return_value = mock_storage
                            mock_storage.get_api_key.return_value = "expired-token"
                            mock_is_valid.return_value = False

                            # Setup device flow mock
                            mock_client = MagicMock()
                            mock_client_class.return_value = mock_client
                            mock_client.start_device_flow = AsyncMock(
                                return_value=DeviceAuthorizationResponse(
                                    device_code="dc123",
                                    user_code="UC-1234",
                                    verification_uri="https://example.com/verify",
                                    verification_uri_complete="https://example.com/verify?code=UC-1234",
                                    expires_in=900,
                                    interval=5,
                                )
                            )
                            mock_client.poll_for_token = AsyncMock(
                                return_value=DeviceTokenResponse(
                                    access_token="new-token",
                                    token_type="Bearer",
                                )
                            )

                            result = await run_login_flow(
                                server_url="https://example.com",
                                callback=callback,
                                open_browser=False,
                            )

                            assert result is True
                            # Token expired is communicated via status message
                            assert any(
                                "expired" in msg.lower()
                                for msg in callback.status_messages
                            )
                            mock_logout.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_new_login_full_flow(self):
        """Test complete new login flow without existing token."""
        callback = MockLoginCallback()

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.device_flow.DeviceFlowClient"
            ) as mock_client_class:
                with patch(
                    "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                ) as mock_fetch:
                    mock_storage = MagicMock()
                    mock_storage_class.return_value = mock_storage
                    mock_storage.get_api_key.return_value = None

                    mock_client = MagicMock()
                    mock_client_class.return_value = mock_client
                    mock_client.start_device_flow = AsyncMock(
                        return_value=DeviceAuthorizationResponse(
                            device_code="dc123",
                            user_code="UC-1234",
                            verification_uri="https://example.com/verify",
                            verification_uri_complete="https://example.com/verify?code=UC-1234",
                            expires_in=900,
                            interval=5,
                        )
                    )
                    mock_client.poll_for_token = AsyncMock(
                        return_value=DeviceTokenResponse(
                            access_token="new-token",
                            token_type="Bearer",
                        )
                    )

                    result = await run_login_flow(
                        server_url="https://example.com",
                        callback=callback,
                        open_browser=False,
                    )

                    assert result is True

                    # Verify callbacks were called
                    assert any("Connecting" in msg for msg in callback.status_messages)
                    assert callback.verification_urls == [
                        ("https://example.com/verify?code=UC-1234", "UC-1234")
                    ]
                    assert any("Waiting" in msg for msg in callback.instructions)
                    # Verify success status message with SUCCESS type
                    assert any("Logged" in msg for msg in callback.status_messages)
                    assert StatusType.SUCCESS in callback.status_types

                    # Verify token was stored
                    mock_storage.store_api_key.assert_called_once_with("new-token")

                    # Verify settings sync was called and communicated via instructions
                    mock_fetch.assert_called_once()
                    assert any(
                        "Settings synchronized" in msg for msg in callback.instructions
                    )

    @pytest.mark.asyncio
    async def test_device_flow_error(self):
        """Test flow when device flow fails."""
        callback = MockLoginCallback()

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.device_flow.DeviceFlowClient"
            ) as mock_client_class:
                mock_storage = MagicMock()
                mock_storage_class.return_value = mock_storage
                mock_storage.get_api_key.return_value = None

                from openhands_cli.auth.device_flow import DeviceFlowError

                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.start_device_flow = AsyncMock(
                    side_effect=DeviceFlowError("Network error")
                )

                result = await run_login_flow(
                    server_url="https://example.com",
                    callback=callback,
                )

                assert result is False
                # Error is communicated via status message with ERROR type
                assert any("Network error" in msg for msg in callback.status_messages)
                assert any("failed" in msg.lower() for msg in callback.status_messages)
                assert StatusType.ERROR in callback.status_types

    @pytest.mark.asyncio
    async def test_browser_open_success(self):
        """Test browser opening on success."""
        callback = MockLoginCallback()

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.device_flow.DeviceFlowClient"
            ) as mock_client_class:
                with patch("webbrowser.open") as mock_browser:
                    with patch(
                        "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                    ):
                        mock_storage = MagicMock()
                        mock_storage_class.return_value = mock_storage
                        mock_storage.get_api_key.return_value = None

                        mock_client = MagicMock()
                        mock_client_class.return_value = mock_client
                        mock_client.start_device_flow = AsyncMock(
                            return_value=DeviceAuthorizationResponse(
                                device_code="dc123",
                                user_code="UC-1234",
                                verification_uri="https://example.com/verify",
                                verification_uri_complete="https://example.com/verify?code=UC-1234",
                                expires_in=900,
                                interval=5,
                            )
                        )
                        mock_client.poll_for_token = AsyncMock(
                            return_value=DeviceTokenResponse(
                                access_token="new-token",
                                token_type="Bearer",
                            )
                        )

                        await run_login_flow(
                            server_url="https://example.com",
                            callback=callback,
                            open_browser=True,
                        )

                        mock_browser.assert_called_once()
                        # Browser success is communicated via status message
                        assert any(
                            "Browser opened" in msg for msg in callback.status_messages
                        )

    @pytest.mark.asyncio
    async def test_browser_open_failure(self):
        """Test handling when browser fails to open."""
        callback = MockLoginCallback()

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.device_flow.DeviceFlowClient"
            ) as mock_client_class:
                with patch("webbrowser.open") as mock_browser:
                    with patch(
                        "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                    ):
                        mock_storage = MagicMock()
                        mock_storage_class.return_value = mock_storage
                        mock_storage.get_api_key.return_value = None

                        mock_client = MagicMock()
                        mock_client_class.return_value = mock_client
                        mock_client.start_device_flow = AsyncMock(
                            return_value=DeviceAuthorizationResponse(
                                device_code="dc123",
                                user_code="UC-1234",
                                verification_uri="https://example.com/verify",
                                verification_uri_complete="https://example.com/verify?code=UC-1234",
                                expires_in=900,
                                interval=5,
                            )
                        )
                        mock_client.poll_for_token = AsyncMock(
                            return_value=DeviceTokenResponse(
                                access_token="new-token",
                                token_type="Bearer",
                            )
                        )

                        mock_browser.side_effect = Exception("No browser available")

                        result = await run_login_flow(
                            server_url="https://example.com",
                            callback=callback,
                            open_browser=True,
                        )

                        assert result is True  # Login should still succeed
                        # Browser failure is communicated via status message
                        assert any(
                            "Could not open browser" in msg
                            for msg in callback.status_messages
                        )

    @pytest.mark.asyncio
    async def test_default_server_url(self):
        """Test that default server URL is used when not provided."""
        callback = MockLoginCallback()

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.utils.is_token_valid") as mock_is_valid:
                with patch("openhands_cli.auth.api_client.fetch_user_data_after_oauth"):
                    with patch.dict(
                        "os.environ", {"OPENHANDS_CLOUD_URL": "https://custom.url"}
                    ):
                        mock_storage = MagicMock()
                        mock_storage_class.return_value = mock_storage
                        mock_storage.get_api_key.return_value = "existing-token"
                        mock_is_valid.return_value = True

                        await run_login_flow(callback=callback)

                        # is_token_valid should be called with the custom URL
                        mock_is_valid.assert_called_once_with(
                            "https://custom.url", "existing-token"
                        )

    @pytest.mark.asyncio
    async def test_null_callback_default(self):
        """Test that NullLoginCallback is used when callback is None."""
        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.utils.is_token_valid") as mock_is_valid:
                with patch("openhands_cli.auth.api_client.fetch_user_data_after_oauth"):
                    mock_storage = MagicMock()
                    mock_storage_class.return_value = mock_storage
                    mock_storage.get_api_key.return_value = "existing-token"
                    mock_is_valid.return_value = True

                    # Should not raise even without callback
                    result = await run_login_flow(
                        server_url="https://example.com",
                        callback=None,
                    )

                    assert result is True

    @pytest.mark.asyncio
    async def test_callback_exception_propagates(self):
        """Test that callback exceptions propagate up.

        This test documents the current behavior - callbacks that
        raise exceptions WILL cause the flow to fail. The exception
        propagates up to the caller.
        """

        class FailingCallback(MockLoginCallback):
            def on_status(
                self, message: str, status_type: StatusType = StatusType.INFO
            ) -> None:
                if "Logged into" in message:
                    raise ValueError("Simulated callback error on login success")
                super().on_status(message, status_type)

        callback = FailingCallback()

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.device_flow.DeviceFlowClient"
            ) as mock_client_class:
                with patch(
                    "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                ) as mock_fetch:
                    mock_storage = MagicMock()
                    mock_storage_class.return_value = mock_storage
                    mock_storage.get_api_key.return_value = None

                    mock_client = MagicMock()
                    mock_client_class.return_value = mock_client
                    mock_client.start_device_flow = AsyncMock(
                        return_value=DeviceAuthorizationResponse(
                            device_code="dc123",
                            user_code="UC-1234",
                            verification_uri="https://example.com/verify",
                            verification_uri_complete="https://example.com/verify?code=UC-1234",
                            expires_in=900,
                            interval=5,
                        )
                    )
                    mock_client.poll_for_token = AsyncMock(
                        return_value=DeviceTokenResponse(
                            access_token="new-token",
                            token_type="Bearer",
                        )
                    )
                    mock_fetch.return_value = None

                    # The exception should propagate up
                    with pytest.raises(
                        ValueError, match="Simulated callback error on login success"
                    ):
                        await run_login_flow(
                            server_url="https://example.com",
                            callback=callback,
                            open_browser=False,
                        )

                    # Verify the token was still stored before the callback failed
                    mock_storage.store_api_key.assert_called_once_with("new-token")
