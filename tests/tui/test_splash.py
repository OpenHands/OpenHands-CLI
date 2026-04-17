"""Tests for splash screen and welcome message functionality."""

from openhands_cli import __version__
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.splash import get_openhands_banner, get_splash_content
from openhands_cli.version_check import VersionInfo


class TestGetOpenHandsBanner:
    """Tests for get_openhands_banner function."""

    def test_banner_contains_openhands_text(self):
        """Test that banner contains OpenHands ASCII art."""
        banner = get_openhands_banner()

        assert isinstance(banner, str)
        assert "___" in banner
        assert "OpenHands" in banner or "_ __" in banner
        assert "\n" in banner

    def test_banner_is_consistent(self):
        """Test that banner is consistent across calls."""
        banner1 = get_openhands_banner()
        banner2 = get_openhands_banner()
        assert banner1 == banner2


class TestGetSplashContent:
    """Tests for get_splash_content function."""

    def test_splash_content_with_default_version(self):
        """Splash should render immediately without performing a version check."""
        content = get_splash_content("test-123", theme=OPENHANDS_THEME)

        assert isinstance(content, dict)
        assert content["version"] == f"OpenHands CLI v{__version__}"
        assert content["update_notice"] is None
        assert "All set up!" in content["status_text"]
        assert "Initialized conversation" in content["conversation_text"]
        assert "test-123" in content["conversation_text"]

    def test_splash_content_structure(self):
        """Test the structure of splash content."""
        content = get_splash_content("test-123", theme=OPENHANDS_THEME)

        expected_keys = [
            "banner",
            "version",
            "status_text",
            "conversation_text",
            "conversation_id",
            "instructions_header",
            "instructions",
            "update_notice",
            "critic_notice",
        ]

        for key in expected_keys:
            assert key in content

        assert isinstance(content["banner"], str)
        assert isinstance(content["version"], str)
        assert isinstance(content["status_text"], str)
        assert isinstance(content["conversation_text"], str)
        assert isinstance(content["conversation_id"], str)
        assert isinstance(content["instructions_header"], str)
        assert isinstance(content["instructions"], list)

    def test_splash_content_includes_update_notice_when_version_info_arrives(self):
        """Update text should render only after background version info arrives."""
        version_info = VersionInfo(
            current_version="1.0.0",
            latest_version="1.1.0",
            needs_update=True,
            error=None,
        )

        content = get_splash_content(
            "test-123",
            theme=OPENHANDS_THEME,
            version_info=version_info,
        )

        assert content["version"] == "OpenHands CLI v1.0.0"
        assert "1.1.0" in content["update_notice"]
        assert "uv tool upgrade openhands" in content["update_notice"]

    def test_splash_content_with_colors(self):
        """Test that splash content includes Rich markup."""
        content = get_splash_content(
            "test-123",
            theme=OPENHANDS_THEME,
            has_critic=True,
        )

        assert "[" in content["banner"] and "]" in content["banner"]
        assert (
            "[" in content["instructions_header"]
            and "]" in content["instructions_header"]
        )
        assert (
            "[" in content["conversation_text"] and "]" in content["conversation_text"]
        )
        assert "Critic + Iterative Refinement Mode" in content["critic_notice"]
