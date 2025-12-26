"""Unit tests for logout command functionality."""

from unittest.mock import MagicMock, patch

from openhands_cli.auth.logout_command import logout_command, run_logout_command


class TestLogoutCommand:
    """Test cases for logout command functionality."""

    def test_logout_command_specific_server_logged_in(self):
        """Test logout from specific server when logged in."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.logout_command.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.logout_command._p") as mock_print:
                mock_storage = MagicMock()
                mock_storage_class.return_value = mock_storage
                mock_storage.remove_api_key.return_value = True  # Was logged in

                result = logout_command(server_url)

                assert result is True
                mock_storage.remove_api_key.assert_called_once()

                # Check that appropriate messages were printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any(
                    "Logged out of OpenHands Cloud" in call for call in print_calls
                )

    def test_logout_command_specific_server_not_logged_in(self):
        """Test logout from specific server when not logged in."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.logout_command.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.logout_command._p") as mock_print:
                mock_storage = MagicMock()
                mock_storage_class.return_value = mock_storage
                mock_storage.remove_api_key.return_value = False  # Was not logged in

                result = logout_command(server_url)

                assert result is True
                mock_storage.remove_api_key.assert_called_once()

                # Check that appropriate messages were printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any(
                    "not logged in to OpenHands Cloud" in call for call in print_calls
                )

    def test_logout_command_global_logged_in(self):
        """Test global logout when logged in."""
        with patch(
            "openhands_cli.auth.logout_command.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.logout_command._p") as mock_print:
                mock_storage = MagicMock()
                mock_storage_class.return_value = mock_storage
                mock_storage.has_api_key.return_value = True  # Is logged in

                result = logout_command(None)

                assert result is True
                mock_storage.has_api_key.assert_called_once()
                mock_storage.remove_api_key.assert_called_once()

                # Check that appropriate messages were printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any(
                    "Logged out of OpenHands Cloud" in call for call in print_calls
                )

    def test_logout_command_global_not_logged_in(self):
        """Test global logout when not logged in."""
        with patch(
            "openhands_cli.auth.logout_command.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.logout_command._p") as mock_print:
                mock_storage = MagicMock()
                mock_storage_class.return_value = mock_storage
                mock_storage.has_api_key.return_value = False  # Not logged in

                result = logout_command(None)

                assert result is True
                mock_storage.has_api_key.assert_called_once()
                mock_storage.remove_api_key.assert_not_called()

                # Check that appropriate messages were printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any(
                    "not logged in to OpenHands Cloud" in call for call in print_calls
                )

    def test_logout_command_exception_handling(self):
        """Test logout command with unexpected exception."""
        server_url = "https://api.example.com"

        with patch(
            "openhands_cli.auth.logout_command.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.logout_command._p") as mock_print:
                mock_storage_class.side_effect = Exception("Unexpected error")

                result = logout_command(server_url)

                assert result is False

                # Check that error message was printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any(
                    "Unexpected error during logout" in call
                    and "Unexpected error" in call
                    for call in print_calls
                )

    def test_logout_command_storage_exception(self):
        """Test logout command when token storage operations fail."""
        with patch(
            "openhands_cli.auth.logout_command.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.logout_command._p") as mock_print:
                mock_storage = MagicMock()
                mock_storage_class.return_value = mock_storage
                mock_storage.has_api_key.side_effect = Exception("Storage error")

                result = logout_command(None)

                assert result is False

                # Check that error message was printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any(
                    "Unexpected error during logout" in call and "Storage error" in call
                    for call in print_calls
                )

    def test_run_logout_command_with_server_url(self):
        """Test synchronous wrapper for logout command with server URL."""
        server_url = "https://api.example.com"

        with patch("openhands_cli.auth.logout_command.logout_command") as mock_logout:
            mock_logout.return_value = True

            result = run_logout_command(server_url)

            assert result is True
            mock_logout.assert_called_once_with(server_url)

    def test_run_logout_command_without_server_url(self):
        """Test synchronous wrapper for logout command without server URL."""
        with patch("openhands_cli.auth.logout_command.logout_command") as mock_logout:
            mock_logout.return_value = True

            result = run_logout_command(None)

            assert result is True
            mock_logout.assert_called_once_with(None)

    def test_run_logout_command_failure(self):
        """Test synchronous wrapper for logout command - failure case."""
        with patch("openhands_cli.auth.logout_command.logout_command") as mock_logout:
            mock_logout.return_value = False

            result = run_logout_command(None)

            assert result is False

    def test_logout_command_default_parameter(self):
        """Test logout command with default parameter (None)."""
        with patch(
            "openhands_cli.auth.logout_command.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.logout_command._p"):
                mock_storage = MagicMock()
                mock_storage_class.return_value = mock_storage
                mock_storage.has_api_key.return_value = False

                # Call without any parameters (should default to None)
                result = logout_command()

                assert result is True
                mock_storage.has_api_key.assert_called_once()

    def test_logout_command_empty_string_server_url(self):
        """Test logout command with empty string server URL."""
        with patch(
            "openhands_cli.auth.logout_command.TokenStorage"
        ) as mock_storage_class:
            with patch("openhands_cli.auth.logout_command._p") as mock_print:
                mock_storage = MagicMock()
                mock_storage_class.return_value = mock_storage
                mock_storage.has_api_key.return_value = True  # User is logged in

                result = logout_command("")

                assert result is True
                mock_storage.remove_api_key.assert_called_once()

                # Empty string is falsy, so it should be treated as global logout
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any(
                    "Logging out from OpenHands Cloud" in call for call in print_calls
                )
                assert any(
                    "Logged out of OpenHands Cloud" in call for call in print_calls
                )

    def test_run_logout_command_default_parameter(self):
        """Test run_logout_command with default parameter."""
        with patch("openhands_cli.auth.logout_command.logout_command") as mock_logout:
            mock_logout.return_value = True

            # Call without any parameters (should default to None)
            result = run_logout_command()

            assert result is True
            mock_logout.assert_called_once_with(None)
