"""Tests for shared text utilities."""

import pytest

from openhands_cli.shared.text_utils import ELLIPSIS, clean_for_display, truncate_text


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_no_truncation_when_within_limit(self):
        """Text within limit should not be truncated."""
        assert truncate_text("hello", max_length=10) == "hello"

    def test_no_truncation_at_exact_limit(self):
        """Text at exact limit should not be truncated."""
        assert truncate_text("hello", max_length=5) == "hello"

    def test_truncate_from_start_with_default_ellipsis(self):
        """Long text should be truncated from start with ellipsis at end."""
        result = truncate_text("hello world", max_length=8)
        assert len(result) == 8
        assert result.endswith(ELLIPSIS)
        assert result == "hello w…"

    def test_truncate_from_end(self):
        """Long text should be truncated from end when from_start=False."""
        result = truncate_text("hello world", max_length=8, from_start=False)
        assert len(result) == 8
        assert result.startswith(ELLIPSIS)
        assert result == "…o world"

    def test_custom_ellipsis(self):
        """Custom ellipsis should be used."""
        result = truncate_text("hello world", max_length=8, ellipsis="...")
        assert result == "hello..."

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert truncate_text("", max_length=10) == ""


class TestCleanForDisplay:
    """Tests for clean_for_display function."""

    def test_strips_whitespace(self):
        """Leading and trailing whitespace should be stripped."""
        assert clean_for_display("  hello  ", max_length=100) == "hello"

    def test_collapses_newlines(self):
        """Newlines should be replaced with spaces."""
        assert clean_for_display("hello\nworld", max_length=100) == "hello world"

    def test_collapses_carriage_returns(self):
        """Carriage returns should be replaced with spaces."""
        assert clean_for_display("hello\rworld", max_length=100) == "hello world"

    def test_strips_and_truncates(self):
        """Text should be stripped and truncated."""
        result = clean_for_display("  hello world  ", max_length=8)
        assert result == "hello w…"

    def test_handles_multiline_text(self):
        """Multiline text should be collapsed and truncated."""
        result = clean_for_display("line1\nline2\nline3", max_length=12)
        assert result == "line1 line2…"


class TestEllipsisConstant:
    """Tests for ELLIPSIS constant."""

    def test_ellipsis_is_single_character(self):
        """ELLIPSIS should be a single unicode character."""
        assert len(ELLIPSIS) == 1
        assert ELLIPSIS == "…"
