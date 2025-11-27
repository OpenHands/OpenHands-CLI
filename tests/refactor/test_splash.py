"""Tests for splash screen and welcome message functionality."""

import unittest.mock as mock

import pytest

from openhands_cli.refactor.splash import get_openhands_banner, get_welcome_message
from openhands_cli.refactor.theme import OPENHANDS_THEME
from openhands_cli.version_check import VersionInfo


class TestGetOpenHandsBanner:
    """Tests for get_openhands_banner function."""

    def test_banner_contains_openhands_text(self):
        """Test that banner contains OpenHands ASCII art."""
        banner = get_openhands_banner()

        # Check that it's a string
        assert isinstance(banner, str)

        # Check that it contains key elements of the ASCII art
        assert "___" in banner
        assert "OpenHands" in banner or "_ __" in banner  # ASCII art representation
        assert "\n" in banner  # Multi-line

    def test_banner_is_consistent(self):
        """Test that banner returns the same content on multiple calls."""
        banner1 = get_openhands_banner()
        banner2 = get_openhands_banner()
        assert banner1 == banner2


class TestGetWelcomeMessage:
    """Tests for get_welcome_message function."""

    def test_welcome_message_without_conversation_id(self):
        """Test welcome message generation without conversation ID."""
        with mock.patch(
            "openhands_cli.refactor.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            message = get_welcome_message(theme=OPENHANDS_THEME)

            # Check basic structure
            assert isinstance(message, str)
            assert "OpenHands CLI v1.0.0" in message
            assert "All set up!" in message
            assert "What do you want to build?" in message
            assert "1. Ask questions, edit files, or run commands." in message
            assert "2. Use @ to look up a file in the folder structure" in message
            assert (
                "3. Type /help for help or / to immediately scroll through "
                "available commands" in message
            )

            # Should contain generated conversation ID
            assert "Initialized conversation" in message

    def test_welcome_message_with_conversation_id(self):
        """Test welcome message generation with conversation ID."""
        with mock.patch(
            "openhands_cli.refactor.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            conversation_id = "test-conversation-123"
            message = get_welcome_message(conversation_id, theme=OPENHANDS_THEME)

            # Check conversation ID is included
            assert f"Initialized conversation {conversation_id}" in message

            # Should still contain the main structure
            assert "OpenHands CLI v1.0.0" in message
            assert "All set up!" in message

    def test_welcome_message_with_update_available(self):
        """Test welcome message when update is available."""
        with mock.patch(
            "openhands_cli.refactor.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.1.0",
                needs_update=True,
                error=None,
            )

            message = get_welcome_message(theme=OPENHANDS_THEME)

            # Check update notification is included
            assert "OpenHands CLI v1.0.0" in message
            assert "⚠ Update available: 1.1.0" in message
            assert "Run 'uv tool upgrade openhands' to update" in message

    def test_welcome_message_no_update_needed(self):
        """Test welcome message when no update is needed."""
        with mock.patch(
            "openhands_cli.refactor.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            message = get_welcome_message(theme=OPENHANDS_THEME)

            # Check no update notification
            assert "OpenHands CLI v1.0.0" in message
            assert "⚠ Update available" not in message
            assert "Run 'uv tool upgrade openhands' to update" not in message

    @pytest.mark.parametrize(
        "conversation_id",
        [
            None,
            "simple-id",
            "complex-conversation-id-with-dashes",
            "123-numeric-id",
            "",
        ],
    )
    def test_welcome_message_various_conversation_ids(self, conversation_id):
        """Test welcome message with various conversation ID formats."""
        with mock.patch(
            "openhands_cli.refactor.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            message = get_welcome_message(conversation_id, theme=OPENHANDS_THEME)

            # Basic structure should always be present
            assert "What do you want to build?" in message
            assert "1. Ask questions, edit files, or run commands." in message
            assert "OpenHands CLI v1.0.0" in message
            assert "All set up!" in message

            # Check conversation ID handling - always present now
            assert "Initialized conversation" in message
            if conversation_id:
                assert f"Initialized conversation {conversation_id}" in message

    def test_welcome_message_includes_banner(self):
        """Test that welcome message includes the OpenHands banner."""
        with mock.patch(
            "openhands_cli.refactor.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            message = get_welcome_message(theme=OPENHANDS_THEME)
            banner = get_openhands_banner()

            # Banner should be included in the message (with or without Rich markup)
            # Check if the plain banner text is present (ignoring Rich markup)
            banner_lines = banner.split("\n")
            for line in banner_lines:
                if line.strip():  # Skip empty lines
                    assert line in message

    def test_welcome_message_structure(self):
        """Test the overall structure of the welcome message."""
        with mock.patch(
            "openhands_cli.refactor.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            message = get_welcome_message(theme=OPENHANDS_THEME)
            lines = message.split("\n")

            # Should have multiple lines
            assert len(lines) > 5

            # Should contain empty lines for spacing
            assert "" in lines

            # Should end with the help instruction
            expected_last_line = (
                "3. Type /help for help or / to immediately scroll through "
                "available commands"
            )
            assert lines[-1] == expected_last_line

    def test_welcome_message_with_colors(self):
        """Test that welcome message includes Rich markup for colors."""
        from openhands_cli.refactor.theme import OPENHANDS_THEME

        with mock.patch(
            "openhands_cli.refactor.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            # Test without conversation ID using theme
            message = get_welcome_message(theme=OPENHANDS_THEME)
            assert f"[{OPENHANDS_THEME.primary}]" in message  # Banner should be colored
            assert "[/]" in message  # Color tags should be closed

            # Test with conversation ID using theme
            message_with_id = get_welcome_message("test-123", theme=OPENHANDS_THEME)
            assert (
                f"[{OPENHANDS_THEME.primary}]" in message_with_id
            )  # Banner should be colored
            assert (
                "Initialized conversation test-123" in message_with_id
            )  # Conversation ID should be present

            # Test that theme parameter is required
            with pytest.raises(TypeError):
                get_welcome_message()  # type: ignore[call-arg] # Should fail without theme parameter
