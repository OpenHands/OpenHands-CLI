"""Unit tests for login command functionality."""

from unittest.mock import MagicMock, patch

import pytest

from openhands_cli.auth.login_command import (
    ConsoleLoginCallback,
    login_command,
    run_login_command,
)


class TestConsoleLoginCallback:
    """Test cases for ConsoleLoginCallback."""

    def test_on_status_success_message(self):
        """Test status message with success indicator."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_status("✓ Success message")

            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "✓ Success message" in call_arg

    def test_on_status_error_message(self):
        """Test status message with error."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_status("Authentication failed")

            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "Authentication failed" in call_arg

    def test_on_verification_url(self):
        """Test verification URL display."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_verification_url("https://example.com/auth", "ABCD-1234")

            assert mock_print.call_count == 3
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("https://example.com/auth" in call for call in calls)
            assert any("ABCD-1234" in call for call in calls)

    def test_on_settings_synced_success(self):
        """Test settings sync success message."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_settings_synced(success=True)

            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "synchronized successfully" in call_arg

    def test_on_settings_synced_error(self):
        """Test settings sync error message."""
        with patch("openhands_cli.auth.login_command.console_print") as mock_print:
            callback = ConsoleLoginCallback()
            callback.on_settings_synced(success=False, error="API error")

            assert mock_print.call_count == 2
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("API error" in call for call in calls)


class TestLoginCommand:
    """Test cases for login command functionality."""

    @pytest.mark.asyncio
    async def test_login_command_delegates_to_run_login_flow(self):
        """Test that login_command delegates to run_login_flow."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.login_command.run_login_flow"
        ) as mock_run_login:
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

        with patch(
            "openhands_cli.auth.login_command.run_login_flow"
        ) as mock_run_login:
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

        with patch(
            "openhands_cli.auth.login_command.run_login_flow"
        ) as mock_run_login:
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
