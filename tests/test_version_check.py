"""Tests for version checking functionality."""

import json
import unittest.mock as mock

from openhands_cli import __version__
from openhands_cli.version_check import VersionInfo, check_for_updates, parse_version


class TestParseVersion:
    """Tests for parse_version function."""

    def test_parse_simple_version(self):
        """Test parsing a simple version string."""
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_parse_major_minor(self):
        """Test parsing major.minor version."""
        assert parse_version("2.5") == (2, 5)

    def test_parse_single_digit(self):
        """Test parsing single digit version."""
        assert parse_version("1") == (1,)

    def test_version_comparison(self):
        """Test version comparison logic."""
        assert parse_version("1.2.3") < parse_version("1.2.4")
        assert parse_version("1.2.3") < parse_version("1.3.0")
        assert parse_version("1.2.3") < parse_version("2.0.0")
        assert parse_version("1.2.3") == parse_version("1.2.3")
        assert parse_version("1.2.4") > parse_version("1.2.3")


class TestCheckForUpdates:
    """Tests for check_for_updates function."""

    def test_dev_version_no_check(self):
        """Test that dev versions don't trigger update checks."""
        with mock.patch("openhands_cli.version_check.__version__", "0.0.0"):
            result = check_for_updates()
            assert result.current_version == "0.0.0"
            assert result.latest_version is None
            assert result.needs_update is False

    def test_network_error_handling(self):
        """Test graceful handling of network errors."""
        with mock.patch(
            "urllib.request.urlopen", side_effect=Exception("Network error")
        ):
            result = check_for_updates()
            assert result.current_version == __version__
            assert result.latest_version is None
            assert result.needs_update is False
            assert result.error is not None

    def test_update_available(self):
        """Test detection of available updates."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {"info": {"version": "999.0.0"}}
        ).encode("utf-8")
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch("openhands_cli.version_check.__version__", "1.0.0"):
                result = check_for_updates()
                assert result.current_version == "1.0.0"
                assert result.latest_version == "999.0.0"
                assert result.needs_update is True
                assert result.error is None

    def test_no_update_needed(self):
        """Test when current version is up to date."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {"info": {"version": "1.0.0"}}
        ).encode("utf-8")
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch("openhands_cli.version_check.__version__", "1.0.0"):
                result = check_for_updates()
                assert result.current_version == "1.0.0"
                assert result.latest_version == "1.0.0"
                assert result.needs_update is False
                assert result.error is None

    def test_current_version_newer(self):
        """Test when current version is newer than PyPI (shouldn't happen normally)."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {"info": {"version": "1.0.0"}}
        ).encode("utf-8")
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch("openhands_cli.version_check.__version__", "2.0.0"):
                result = check_for_updates()
                assert result.current_version == "2.0.0"
                assert result.latest_version == "1.0.0"
                assert result.needs_update is False
                assert result.error is None

    def test_timeout_parameter(self):
        """Test that timeout parameter is used correctly."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {"info": {"version": "1.0.0"}}
        ).encode("utf-8")
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch(
            "urllib.request.urlopen", return_value=mock_response
        ) as mock_urlopen:
            check_for_updates(timeout=5.0)
            # Verify that urlopen was called with the timeout parameter
            args, kwargs = mock_urlopen.call_args
            assert kwargs.get("timeout") == 5.0 or (len(args) > 1 and args[1] == 5.0)

    def test_version_info_structure(self):
        """Test VersionInfo named tuple structure."""
        info = VersionInfo(
            current_version="1.0.0",
            latest_version="1.0.1",
            needs_update=True,
            error=None,
        )
        assert info.current_version == "1.0.0"
        assert info.latest_version == "1.0.1"
        assert info.needs_update is True
        assert info.error is None
