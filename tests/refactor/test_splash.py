"""Tests for splash screen and welcome message functionality."""

import unittest.mock as mock

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.splash import (
    get_openhands_banner,
    get_splash_content,
)
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
        """Test that banner is consistent across calls."""
        banner1 = get_openhands_banner()
        banner2 = get_openhands_banner()
        assert banner1 == banner2


class TestGetSplashContent:
    """Tests for get_splash_content function."""

    def test_splash_content_with_conversation_id(self):
        """Test splash content generation with conversation ID."""
        with mock.patch(
            "openhands_cli.tui.content.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            content = get_splash_content("test-123", theme=OPENHANDS_THEME)

            # Check basic structure
            assert isinstance(content, dict)
            assert "version" in content
            assert "OpenHands CLI v1.0.0" in content["version"]
            assert "status_text" in content
            assert "All set up!" in content["status_text"]
            assert "instructions_header" in content
            assert "What do you want to build?" in content["instructions_header"]
            assert "instructions" in content
            assert (
                "1. Ask questions, edit files, or run commands."
                in content["instructions"][0]
            )
            assert (
                "2. Use @ to look up a file in the folder structure"
                in content["instructions"][1]
            )

            # Should contain conversation ID
            assert "conversation_text" in content
            assert "Initialized conversation" in content["conversation_text"]
            assert "test-123" in content["conversation_text"]

    def test_splash_content_structure(self):
        """Test the structure of splash content."""
        with mock.patch(
            "openhands_cli.tui.content.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            content = get_splash_content("test-123", theme=OPENHANDS_THEME)

            # Check that all expected keys are present
            expected_keys = [
                "banner",
                "version",
                "status_text",
                "conversation_text",
                "conversation_id",
                "instructions_header",
                "instructions",
            ]

            for key in expected_keys:
                assert key in content

            # Check types
            assert isinstance(content["banner"], str)
            assert isinstance(content["version"], str)
            assert isinstance(content["status_text"], str)
            assert isinstance(content["conversation_text"], str)
            assert isinstance(content["conversation_id"], str)
            assert isinstance(content["instructions_header"], str)
            assert isinstance(content["instructions"], list)

    def test_splash_content_includes_banner(self):
        """Test that splash content includes the OpenHands banner."""
        with mock.patch(
            "openhands_cli.tui.content.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            content = get_splash_content("test-123", theme=OPENHANDS_THEME)

            # Should include banner elements
            banner = content["banner"]
            assert "OpenHands" in banner or "_ __" in banner
            assert "___" in banner

    def test_splash_content_with_colors(self):
        """Test that splash content includes color markup."""
        with mock.patch(
            "openhands_cli.tui.content.splash.check_for_updates"
        ) as mock_check:
            mock_check.return_value = VersionInfo(
                current_version="1.0.0",
                latest_version="1.0.0",
                needs_update=False,
                error=None,
            )

            content = get_splash_content("test-123", theme=OPENHANDS_THEME)

            # Should contain Rich markup for colors
            assert "[" in content["banner"] and "]" in content["banner"]
            assert (
                "[" in content["instructions_header"]
                and "]" in content["instructions_header"]
            )
            assert (
                "[" in content["conversation_text"]
                and "]" in content["conversation_text"]
            )
