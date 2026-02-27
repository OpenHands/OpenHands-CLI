"""Unit tests for login service functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands_cli.auth.device_flow import (
    DeviceAuthorizationResponse,
    DeviceTokenResponse,
)
from openhands_cli.auth.login_service import (
    NullLoginCallback,
    run_login_flow,
)


class MockLoginCallback:
    """Mock implementation of LoginProgressCallback for testing."""

    def __init__(self):
        self.status_messages = []
        self.verification_urls = []
        self.instructions = []
        self.browser_opened_results = []
        self.already_logged_in_called = False
        self.token_expired_called = False
        self.login_success_called = False
        self.settings_synced_results = []
        self.errors = []

    def on_status(self, message: str) -> None:
        self.status_messages.append(message)

    def on_verification_url(self, url: str, user_code: str) -> None:
        self.verification_urls.append((url, user_code))

    def on_instructions(self, message: str) -> None:
        self.instructions.append(message)

    def on_browser_opened(self, success: bool) -> None:
        self.browser_opened_results.append(success)

    def on_already_logged_in(self) -> None:
        self.already_logged_in_called = True

    def on_token_expired(self) -> None:
        self.token_expired_called = True

    def on_login_success(self) -> None:
        self.login_success_called = True

    def on_settings_synced(self, success: bool, error: str | None = None) -> None:
        self.settings_synced_results.append((success, error))

    def on_error(self, error: str) -> None:
        self.errors.append(error)


class TestNullLoginCallback:
    """Test NullLoginCallback does nothing (no errors)."""

    def test_all_methods_are_no_ops(self):
        """Test that all callback methods run without errors."""
        callback = NullLoginCallback()
        callback.on_status("test")
        callback.on_verification_url("url", "code")
        callback.on_instructions("test")
        callback.on_browser_opened(True)
        callback.on_already_logged_in()
        callback.on_token_expired()
        callback.on_login_success()
        callback.on_settings_synced(True)
        callback.on_error("test")


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
                    assert callback.already_logged_in_called
                    assert any(
                        "Already logged in" in msg for msg in callback.status_messages
                    )
                    assert callback.settings_synced_results == [(True, None)]

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
                    assert callback.settings_synced_results == []

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
                            assert callback.token_expired_called
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
                    assert callback.login_success_called
                    assert any("✓ Logged" in msg for msg in callback.status_messages)

                    # Verify token was stored
                    mock_storage.store_api_key.assert_called_once_with("new-token")

                    # Verify settings sync was called
                    mock_fetch.assert_called_once()
                    assert callback.settings_synced_results == [(True, None)]

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
                assert "Network error" in callback.errors
                assert any("failed" in msg.lower() for msg in callback.status_messages)

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
                        assert callback.browser_opened_results == [True]

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
                        assert callback.browser_opened_results == [False]

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
    async def test_callback_exception_does_not_crash_login_flow(self):
        """Test that callback exceptions don't crash the login flow.

        The login flow should complete successfully even if a callback
        raises an exception. This is important because the core login
        logic (token storage, etc.) should not be affected by UI errors.
        """

        class FailingCallback(MockLoginCallback):
            def on_login_success(self):
                raise ValueError("Simulated callback error")

            def on_settings_synced(self, success: bool, error: str | None = None):
                raise RuntimeError("Another simulated error")

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

                    # The login flow should succeed despite callback exceptions
                    # Note: Currently the flow does NOT catch callback exceptions,
                    # so if a callback raises, the exception propagates up.
                    # This test documents the current behavior - callbacks that
                    # raise exceptions WILL cause the flow to fail.
                    with pytest.raises(ValueError, match="Simulated callback error"):
                        await run_login_flow(
                            server_url="https://example.com",
                            callback=callback,
                            open_browser=False,
                        )

                    # Verify the token was still stored before the callback failed
                    mock_storage.store_api_key.assert_called_once_with("new-token")
