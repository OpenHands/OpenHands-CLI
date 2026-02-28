"""Unit tests for login command functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands_cli.auth.device_flow import (
    DeviceAuthorizationResponse,
    DeviceFlowError,
    DeviceTokenResponse,
)
from openhands_cli.auth.login_command import (
    ConsoleLoginCallback,
    login_command,
    run_login_command,
)
from openhands_cli.auth.login_service import StatusType


class TestConsoleLoginCallback:
    """Test cases for ConsoleLoginCallback."""

    def test_on_status_success_type(self):
        """Test status message with success type uses success styling."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_status("Login successful!", StatusType.SUCCESS)

            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "Login successful!" in call_arg
            # Should use success color from theme
            assert "green" in call_arg.lower() or "success" in call_arg.lower()

    def test_on_status_error_type(self):
        """Test status message with error type uses error styling."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_status("Authentication failed", StatusType.ERROR)

            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "Authentication failed" in call_arg

    def test_on_status_warning_type(self):
        """Test status message with warning type uses warning styling."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_status("Token expired", StatusType.WARNING)

            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "Token expired" in call_arg

    def test_on_status_info_type(self):
        """Test status message with info type (default) uses info styling."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_status("Connecting...", StatusType.INFO)

            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "Connecting..." in call_arg

    def test_on_status_default_type(self):
        """Test status message without type defaults to INFO."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_status("Some message")

            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "Some message" in call_arg

    def test_on_verification_url(self):
        """Test verification URL display."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_verification_url("https://example.com/auth", "ABCD-1234")

            assert mock_print.call_count == 3
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("https://example.com/auth" in call for call in calls)
            assert any("ABCD-1234" in call for call in calls)

    def test_on_instructions_success(self):
        """Test instructions message with success indicator."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_instructions("✓ Settings synchronized!")

            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "Settings synchronized" in call_arg

    def test_on_instructions_warning(self):
        """Test instructions message with warning content."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_instructions("Warning: Could not sync settings")

            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "Could not sync settings" in call_arg


class TestLoginCommand:
    """Test cases for login command functionality."""

    @pytest.mark.asyncio
    async def test_login_command_delegates_to_run_login_flow(self):
        """Test that login_command delegates to run_login_flow."""
        server_url = "https://api.example.com"

        with patch("openhands_cli.auth.login_command.run_login_flow") as mock_run_login:
            with patch("openhands_cli.auth.login_command.console_print"):
                mock_run_login.return_value = True

                result = await login_command(server_url)

                assert result is True
                mock_run_login.assert_called_once()
                # Check that server_url was passed
                call_kwargs = mock_run_login.call_args[1]
                assert call_kwargs["server_url"] == server_url
                assert isinstance(call_kwargs["callback"], ConsoleLoginCallback)

    @pytest.mark.asyncio
    async def test_login_command_skip_settings_sync(self):
        """Test login command with skip_settings_sync=True."""
        server_url = "https://api.example.com"

        with patch("openhands_cli.auth.login_command.run_login_flow") as mock_run_login:
            with patch("openhands_cli.auth.login_command.console_print"):
                mock_run_login.return_value = True

                result = await login_command(server_url, skip_settings_sync=True)

                assert result is True
                call_kwargs = mock_run_login.call_args[1]
                assert call_kwargs["skip_settings_sync"] is True

    @pytest.mark.asyncio
    async def test_login_command_returns_false_on_failure(self):
        """Test login command returns False when run_login_flow fails."""
        server_url = "https://api.example.com"

        with patch("openhands_cli.auth.login_command.run_login_flow") as mock_run_login:
            with patch("openhands_cli.auth.login_command.console_print"):
                mock_run_login.return_value = False

                result = await login_command(server_url)

                assert result is False

    def test_run_login_command_success(self):
        """Test synchronous wrapper for login command - success case."""
        server_url = "https://api.example.com"

        with patch("openhands_cli.auth.login_command.asyncio.run") as mock_run:
            mock_run.return_value = True

            result = run_login_command(server_url)

            assert result is True
            mock_run.assert_called_once()

    def test_run_login_command_keyboard_interrupt(self):
        """Test synchronous wrapper for login command - keyboard interrupt."""
        server_url = "https://api.example.com"

        with patch("openhands_cli.auth.login_command.asyncio.run") as mock_run:
            with patch("openhands_cli.auth.login_command.console_print") as mock_print:
                mock_run.side_effect = KeyboardInterrupt()

                result = run_login_command(server_url)

                assert result is False
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any("cancelled by user" in call for call in print_calls)

    def test_run_login_command_failure(self):
        """Test synchronous wrapper for login command - failure case."""
        server_url = "https://api.example.com"

        with patch("openhands_cli.auth.login_command.asyncio.run") as mock_run:
            mock_run.return_value = False

            result = run_login_command(server_url)

            assert result is False


class TestLoginCommandIntegration:
    """Integration tests for login_command testing full behavior flows.

    These tests verify the complete behavior of login_command through real
    code paths (not mocking run_login_flow), while still mocking external
    dependencies like TokenStorage, device flow, and API client.
    """

    @pytest.mark.asyncio
    async def test_login_command_existing_valid_token(self):
        """Test login command when user already has a valid token."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.utils.is_token_valid") as mock_is_valid:
                with patch(
                    "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                ) as mock_fetch:
                    with patch("openhands_cli.auth.login_command.console_print"):
                        mock_storage = MagicMock()
                        mock_storage_class.return_value = mock_storage
                        mock_storage.get_api_key.return_value = "existing-api-key"
                        mock_is_valid.return_value = True
                        mock_fetch.return_value = {"settings": {}}

                        result = await login_command(server_url)

                        assert result is True
                        mock_is_valid.assert_called_once_with(
                            server_url, "existing-api-key"
                        )
                        mock_fetch.assert_called_once_with(
                            server_url, "existing-api-key"
                        )

    @pytest.mark.asyncio
    async def test_login_command_expired_token_triggers_logout(self):
        """Test login command when existing token is expired triggers logout."""
        server_url = "https://api.example.com"

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
                            with patch("openhands_cli.auth.login_command.console_print"):
                                mock_storage = MagicMock()
                                mock_storage_class.return_value = mock_storage
                                mock_storage.get_api_key.return_value = "expired-token"
                                mock_is_valid.return_value = False

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

                                result = await login_command(server_url)

                                assert result is True
                                mock_logout.assert_called_once_with(server_url)
                                mock_storage.store_api_key.assert_called_once_with(
                                    "new-token"
                                )

    @pytest.mark.asyncio
    async def test_login_command_new_device_flow_authentication(self):
        """Test login command with new device flow authentication."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.device_flow.DeviceFlowClient"
            ) as mock_client_class:
                with patch(
                    "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                ) as mock_fetch:
                    with patch("openhands_cli.auth.login_command.console_print"):
                        with patch("webbrowser.open"):
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
                                    access_token="new-api-key",
                                    token_type="Bearer",
                                    expires_in=3600,
                                )
                            )
                            mock_fetch.return_value = {"settings": {}}

                            result = await login_command(server_url)

                            assert result is True
                            mock_client.start_device_flow.assert_called_once()
                            mock_client.poll_for_token.assert_called_once_with(
                                "dc123", 5
                            )
                            mock_storage.store_api_key.assert_called_once_with(
                                "new-api-key"
                            )
                            mock_fetch.assert_called_once_with(
                                server_url, "new-api-key"
                            )

    @pytest.mark.asyncio
    async def test_login_command_device_flow_error(self):
        """Test login command when device flow fails."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.device_flow.DeviceFlowClient"
            ) as mock_client_class:
                with patch(
                    "openhands_cli.auth.login_command.console_print"
                ) as mock_print:
                    mock_storage = MagicMock()
                    mock_storage_class.return_value = mock_storage
                    mock_storage.get_api_key.return_value = None

                    mock_client = MagicMock()
                    mock_client_class.return_value = mock_client
                    mock_client.start_device_flow = AsyncMock(
                        side_effect=DeviceFlowError("Network error")
                    )

                    result = await login_command(server_url)

                    assert result is False
                    # Verify error was printed
                    print_calls = [call[0][0] for call in mock_print.call_args_list]
                    assert any("Network error" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_login_command_api_client_error_during_settings_sync(self):
        """Test login command when API client fails during settings sync."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.utils.is_token_valid") as mock_is_valid:
                with patch(
                    "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                ) as mock_fetch:
                    with patch("openhands_cli.auth.login_command.console_print"):
                        from openhands_cli.auth.api_client import ApiClientError

                        mock_storage = MagicMock()
                        mock_storage_class.return_value = mock_storage
                        mock_storage.get_api_key.return_value = "existing-api-key"
                        mock_is_valid.return_value = True
                        mock_fetch.side_effect = ApiClientError("API error")

                        # Login should still succeed even if settings sync fails
                        result = await login_command(server_url)

                        assert result is True
                        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_command_skip_settings_sync(self):
        """Test login command with skip_settings_sync=True."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.utils.is_token_valid") as mock_is_valid:
                with patch(
                    "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                ) as mock_fetch:
                    with patch("openhands_cli.auth.login_command.console_print"):
                        mock_storage = MagicMock()
                        mock_storage_class.return_value = mock_storage
                        mock_storage.get_api_key.return_value = "existing-api-key"
                        mock_is_valid.return_value = True

                        result = await login_command(
                            server_url, skip_settings_sync=True
                        )

                        assert result is True
                        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_command_complete_flow_with_token_storage(self):
        """Test complete successful login flow with token storage and data fetch."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.device_flow.DeviceFlowClient"
            ) as mock_client_class:
                with patch(
                    "openhands_cli.auth.api_client.fetch_user_data_after_oauth"
                ) as mock_fetch:
                    with patch(
                        "openhands_cli.auth.login_command.console_print"
                    ) as mock_print:
                        with patch("webbrowser.open"):
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
                                    access_token="new-api-key",
                                    token_type="Bearer",
                                    expires_in=3600,
                                )
                            )
                            mock_fetch.return_value = {"settings": {}}

                            result = await login_command(server_url)

                            assert result is True

                            # Verify complete flow
                            mock_client.start_device_flow.assert_called_once()
                            mock_client.poll_for_token.assert_called_once()
                            mock_storage.store_api_key.assert_called_once_with(
                                "new-api-key"
                            )
                            mock_fetch.assert_called_once_with(
                                server_url, "new-api-key"
                            )

                            # Verify status messages were printed
                            print_calls = [
                                call[0][0] for call in mock_print.call_args_list
                            ]
                            assert any(
                                "Logging in" in call for call in print_calls
                            )

    @pytest.mark.asyncio
    async def test_login_command_poll_for_token_error(self):
        """Test login command when polling for token fails."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.token_storage.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.device_flow.DeviceFlowClient"
            ) as mock_client_class:
                with patch("openhands_cli.auth.login_command.console_print"):
                    with patch("webbrowser.open"):
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
                            side_effect=DeviceFlowError("Authorization expired")
                        )

                        result = await login_command(server_url)

                        assert result is False
                        mock_storage.store_api_key.assert_not_called()
