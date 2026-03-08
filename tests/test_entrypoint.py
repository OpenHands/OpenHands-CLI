"""Tests for entrypoint handle_resume_logic keyword normalization (BUG-003)."""

import argparse
from unittest.mock import MagicMock, patch

from openhands_cli.entrypoint import handle_resume_logic


def _make_args(resume: str | None = None, last: bool = False) -> argparse.Namespace:
    """Create a minimal Namespace matching the CLI's argparse output."""
    return argparse.Namespace(resume=resume, last=last)


class TestHandleResumeLogicNormalization:
    """Test that `--resume last` (case-insensitive) normalizes to the --last path."""

    @patch("openhands_cli.conversations.store.local.LocalFileStore")
    def test_resume_last_lowercase(self, mock_store_cls: MagicMock) -> None:
        """--resume last → sets args.last=True and delegates to --last code path."""
        mock_store = mock_store_cls.return_value
        mock_conv = MagicMock()
        mock_conv.id = "abc-123"
        mock_store.list_conversations.return_value = [mock_conv]

        args = _make_args(resume="last", last=False)
        result = handle_resume_logic(args)

        assert args.last is True
        assert result == "abc-123"
        mock_store.list_conversations.assert_called_once_with(limit=1)

    @patch("openhands_cli.conversations.store.local.LocalFileStore")
    def test_resume_LAST_uppercase(self, mock_store_cls: MagicMock) -> None:
        """--resume LAST → case-insensitive normalization."""
        mock_store = mock_store_cls.return_value
        mock_conv = MagicMock()
        mock_conv.id = "abc-123"
        mock_store.list_conversations.return_value = [mock_conv]

        args = _make_args(resume="LAST", last=False)
        result = handle_resume_logic(args)

        assert args.last is True
        assert result == "abc-123"

    @patch("openhands_cli.conversations.store.local.LocalFileStore")
    def test_resume_Last_mixed_case(self, mock_store_cls: MagicMock) -> None:
        """--resume Last → mixed-case normalization."""
        mock_store = mock_store_cls.return_value
        mock_conv = MagicMock()
        mock_conv.id = "abc-123"
        mock_store.list_conversations.return_value = [mock_conv]

        args = _make_args(resume="Last", last=False)
        result = handle_resume_logic(args)

        assert args.last is True
        assert result == "abc-123"

    def test_resume_valid_uuid_unchanged(self) -> None:
        """--resume <uuid> → passed through unchanged, args.last stays False."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        args = _make_args(resume=test_uuid, last=False)
        result = handle_resume_logic(args)

        assert args.last is False
        assert result == test_uuid

    def test_resume_none_new_conversation(self) -> None:
        """No --resume flag → returns None (new conversation)."""
        args = _make_args(resume=None, last=False)
        result = handle_resume_logic(args)

        assert result is None
