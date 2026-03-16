"""Tests for truncation note stripping functionality."""

from __future__ import annotations

import pytest

from openhands_cli.acp_impl.events.shared_event_handler import _strip_truncation_notes


class TestStripTruncationNotes:
    """Test _strip_truncation_notes function."""

    def test_no_notes_returns_unchanged(self):
        """Text without notes should be returned unchanged."""
        text = "This is normal output"
        assert _strip_truncation_notes(text) == text

    def test_single_line_note_removed(self):
        """Single-line NOTE tag should be removed."""
        text = 'Some output<NOTE>Due to the max output limit, only part of this directory has been shown to you. You should use `ls -la` instead to view large directories incrementally.</NOTE>'
        result = _strip_truncation_notes(text)
        assert result == "Some output"
        assert "<NOTE>" not in result
        assert "max output limit" not in result

    def test_response_clipped_note_removed(self):
        """<response clipped> prefix with NOTE tag should be removed."""
        text = 'Some output<response clipped><NOTE>Due to the max output limit, only part of this directory has been shown to you. You should use `ls -la` instead to view large directories incrementally.</NOTE>'
        result = _strip_truncation_notes(text)
        assert result == "Some output"
        assert "<response clipped>" not in result
        assert "<NOTE>" not in result
        assert "max output limit" not in result

    def test_multiline_note_removed(self):
        """Multi-line NOTE tag should be removed."""
        text = """Directory listing:
/home/user/file1.txt
/home/user/file2.txt
<NOTE>Due to the max output limit, only part of this directory has been shown to you. 
You should use `ls -la` instead to view large directories incrementally.</NOTE>"""
        result = _strip_truncation_notes(text)
        assert result == "Directory listing:\n/home/user/file1.txt\n/home/user/file2.txt"
        assert "<NOTE>" not in result

    def test_multiple_notes_removed(self):
        """Multiple NOTE tags should all be removed."""
        text = "Start<NOTE>note1</NOTE>middle<NOTE>note2</NOTE>end"
        result = _strip_truncation_notes(text)
        assert result == "Startmiddleend"

    def test_trailing_whitespace_removed(self):
        """Trailing whitespace should be removed after stripping notes."""
        text = "Content with note<NOTE>truncation</NOTE>  \n  "
        result = _strip_truncation_notes(text)
        assert result == "Content with note"
        assert not result.endswith(" ")
        assert not result.endswith("\n")

    def test_empty_note_tag_removed(self):
        """Empty NOTE tags should be removed."""
        text = "Output<NOTE></NOTE>"
        result = _strip_truncation_notes(text)
        assert result == "Output"

    def test_preserves_other_content(self):
        """Non-NOTE content should be preserved."""
        text = "File listing:\n/path/to/file1\n/path/to/file2<NOTE>truncated</NOTE>\n<NOTE>more truncation</NOTE>"
        result = _strip_truncation_notes(text)
        assert "/path/to/file1" in result
        assert "/path/to/file2" in result
        assert "<NOTE>" not in result

    def test_note_with_special_characters(self):
        """NOTE with special regex characters should be handled safely."""
        text = 'Output<NOTE>Note with [special] (characters) and *regex* .stuff</NOTE>result'
        result = _strip_truncation_notes(text)
        assert result == "Outputresult"
        assert "<NOTE>" not in result

    def test_case_sensitive_note_tag(self):
        """NOTE tag should be case-sensitive (uppercase only)."""
        text = "Output<note>lowercase</note><NOTE>UPPERCASE</NOTE>"
        result = _strip_truncation_notes(text)
        # lowercase note tags should NOT be removed (case-sensitive)
        assert "<note>lowercase</note>" in result
        # uppercase NOTE tags should be removed
        assert "<NOTE>" not in result

    def test_real_world_example(self):
        """Test with a real-world file listing scenario."""
        text = """drwxr-xr-x  2 user user  4096 Jan  1 12:00 .
drwxr-xr-x 10 user user  4096 Jan  1 12:00 ..
-rw-r--r--  1 user user 12345 Jan  1 12:00 file1.py
-rw-r--r--  1 user user 67890 Jan  1 12:00 file2.py
<NOTE>Due to the max output limit, only part of this directory has been shown to you. You should use `ls -la` instead to view large directories incrementally.</NOTE>"""
        result = _strip_truncation_notes(text)
        assert "file1.py" in result
        assert "file2.py" in result
        assert "drwxr-xr-x" in result
        assert "<NOTE>" not in result
        assert "max output limit" not in result

    def test_real_world_example_with_response_clipped(self):
        """Test with a real-world file listing scenario including <response clipped>."""
        text = """drwxr-xr-x  2 user user  4096 Jan  1 12:00 .
drwxr-xr-x 10 user user  4096 Jan  1 12:00 ..
-rw-r--r--  1 user user 12345 Jan  1 12:00 file1.py
-rw-r--r--  1 user user 67890 Jan  1 12:00 file2.py
<response clipped><NOTE>Due to the max output limit, only part of this directory has been shown to you. You should use `ls -la` instead to view large directories incrementally.</NOTE>"""
        result = _strip_truncation_notes(text)
        assert "file1.py" in result
        assert "file2.py" in result
        assert "drwxr-xr-x" in result
        assert "<response clipped>" not in result
        assert "<NOTE>" not in result
        assert "max output limit" not in result
