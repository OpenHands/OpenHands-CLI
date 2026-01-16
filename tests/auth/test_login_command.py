"""Unit tests for login command functionality."""

from unittest.mock import MagicMock, patch

import pytest

from openhands_cli.auth.login_command import (
    _fetch_user_data_with_context,
    login_command,
    run_login_command,
)


class TestLoginCommand:
    """Test cases for login command functionality."""

    @pytest.mark.asyncio
    async def test_fetch_user_data_with_context_already_logged_in_success(self):
        """Test fetching user data when already logged in - success case."""
        server_url = "https://api.example.com"
        api_key = "test-api-key"

        with patch(
            "openhands_cli.auth.login_command.fetch_user_data_after_oauth"
        ) as mock_fetch:
            with patch("openhands_cli.auth.login_command._p") as mock_print:
                mock_fetch.return_value = {"llm_api_key": "llm-key", "settings": {}}

                await _fetch_user_data_with_context(
                    server_url, api_key, already_logged_in=True
                )

                mock_fetch.assert_called_once_with(
                    server_url, api_key, sync_settings=None, silent=False
                )

                # Check that appropriate messages were printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any("already logged in" in call for call in print_calls)
                assert any("synchronized successfully" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_fetch_user_data_with_context_new_login_success(self):
        """Test fetching user data for new login - success case."""
        server_url = "https://api.example.com"
        api_key = "test-api-key"

        with patch(
            "openhands_cli.auth.login_command.fetch_user_data_after_oauth"
        ) as mock_fetch:
            with patch("openhands_cli.auth.login_command._p") as mock_print:
                mock_fetch.return_value = {"llm_api_key": "llm-key", "settings": {}}

                await _fetch_user_data_with_context(
                    server_url, api_key, already_logged_in=False
                )

                mock_fetch.assert_called_once_with(
                    server_url, api_key, sync_settings=None, silent=False
                )

                # Check that appropriate messages were printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any("synchronized successfully" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_fetch_user_data_with_context_api_error(self):
        """Test fetching user data with API client error."""
        server_url = "https://api.example.com"
        api_key = "test-api-key"

        with patch(
            "openhands_cli.auth.login_command.fetch_user_data_after_oauth"
        ) as mock_fetch:
            with patch("openhands_cli.auth.login_command._p") as mock_print:
                from openhands_cli.auth.api_client import ApiClientError

                mock_fetch.side_effect = ApiClientError("API error")

                await _fetch_user_data_with_context(
                    server_url, api_key, already_logged_in=False
                )

                # Should print warning but not raise
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any(
                    "Warning" in call and "API error" in call for call in print_calls
                )

    @pytest.mark.asyncio
    async def test_login_command_existing_token(self):
        """Test login command when user already has a token."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.login_command.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.login_command._fetch_user_data_with_context"
            ) as mock_fetch:
                with patch("openhands_cli.auth.login_command._p"):
                    mock_storage = MagicMock()
                    mock_storage_class.return_value = mock_storage
                    mock_storage.get_api_key.return_value = "existing-api-key"

                    result = await login_command(server_url)

                    assert result is True
                    mock_fetch.assert_called_once_with(
                        server_url,
                        "existing-api-key",
                        already_logged_in=True,
                        sync_settings=None,
                        silent=False,
                    )

    @pytest.mark.asyncio
    async def test_login_command_new_login_success(self):
        """Test login command with new device flow authentication."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.login_command.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.login_command.authenticate_with_device_flow"
            ) as mock_auth:
                with patch(
                    "openhands_cli.auth.login_command._fetch_user_data_with_context"
                ) as mock_fetch:
                    with patch("openhands_cli.auth.login_command._p"):
                        mock_storage = MagicMock()
                        mock_storage_class.return_value = mock_storage
                        mock_storage.get_api_key.return_value = (
                            None  # No existing token
                        )

                        mock_auth.return_value = {
                            "access_token": "new-api-key",
                            "token_type": "Bearer",
                        }

                        result = await login_command(server_url)

                        assert result is True
                        mock_auth.assert_called_once_with(server_url)
                        mock_storage.store_api_key.assert_called_once_with(
                            "new-api-key"
                        )
                        mock_fetch.assert_called_once_with(
                            server_url,
                            "new-api-key",
                            already_logged_in=False,
                            sync_settings=None,
                            silent=False,
                        )

    @pytest.mark.asyncio
    async def test_login_command_device_flow_error(self):
        """Test login command when device flow fails."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.login_command.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.login_command.authenticate_with_device_flow"
            ) as mock_auth:
                with patch("openhands_cli.auth.login_command._p") as mock_print:
                    mock_storage = MagicMock()
                    mock_storage_class.return_value = mock_storage
                    mock_storage.get_api_key.return_value = None

                    from openhands_cli.auth.device_flow import DeviceFlowError

                    mock_auth.side_effect = DeviceFlowError("Authentication failed")

                    result = await login_command(server_url)

                    assert result is False
                    print_calls = [call[0][0] for call in mock_print.call_args_list]
                    assert any("Authentication failed" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_login_command_no_access_token(self):
        """Test login command when OAuth response has no access token."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.login_command.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.login_command.authenticate_with_device_flow"
            ) as mock_auth:
                with patch("openhands_cli.auth.login_command._p") as mock_print:
                    mock_storage = MagicMock()
                    mock_storage_class.return_value = mock_storage
                    mock_storage.get_api_key.return_value = None

                    mock_auth.return_value = {"token_type": "Bearer"}  # No access_token

                    result = await login_command(server_url)

                    assert result is True  # Still considered successful
                    mock_storage.store_api_key.assert_not_called()
                    print_calls = [call[0][0] for call in mock_print.call_args_list]
                    assert any("No access token found" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_login_command_empty_access_token(self):
        """Test login command when OAuth response has empty access token."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.login_command.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.login_command.authenticate_with_device_flow"
            ) as mock_auth:
                with patch(
                    "openhands_cli.auth.login_command._fetch_user_data_with_context"
                ) as mock_fetch:
                    with patch("openhands_cli.auth.login_command._p"):
                        mock_storage = MagicMock()
                        mock_storage_class.return_value = mock_storage
                        mock_storage.get_api_key.return_value = None

                        mock_auth.return_value = {
                            "access_token": "",
                            "token_type": "Bearer",
                        }

                        result = await login_command(server_url)

                        assert result is True
                        mock_storage.store_api_key.assert_not_called()
                        mock_fetch.assert_not_called()

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
            with patch("openhands_cli.auth.login_command._p") as mock_print:
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

    @pytest.mark.asyncio
    async def test_login_command_with_successful_token_storage_and_fetch(self):
        """Test complete successful login flow with token storage and data fetch."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.login_command.TokenStorage"
        ) as mock_storage_class:
            with patch(
                "openhands_cli.auth.login_command.authenticate_with_device_flow"
            ) as mock_auth:
                with patch(
                    "openhands_cli.auth.login_command._fetch_user_data_with_context"
                ) as mock_fetch:
                    with patch("openhands_cli.auth.login_command._p") as mock_print:
                        mock_storage = MagicMock()
                        mock_storage_class.return_value = mock_storage
                        mock_storage.get_api_key.return_value = None

                        mock_auth.return_value = {
                            "access_token": "new-api-key",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }

                        result = await login_command(server_url)

                        assert result is True

                        # Verify the complete flow
                        mock_storage.get_api_key.assert_called_once()
                        mock_auth.assert_called_once_with(server_url)
                        mock_storage.store_api_key.assert_called_once_with(
                            "new-api-key"
                        )
                        mock_fetch.assert_called_once_with(
                            server_url,
                            "new-api-key",
                            already_logged_in=False,
                            sync_settings=None,
                            silent=False,
                        )

                        # Verify success messages
                        print_calls = [call[0][0] for call in mock_print.call_args_list]
                        assert any(
                            "Logged into OpenHands Cloud" in call
                            for call in print_calls
                        )
                        assert any("stored securely" in call for call in print_calls)
