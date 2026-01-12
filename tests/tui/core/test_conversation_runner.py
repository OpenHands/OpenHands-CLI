"""Tests for ConversationRunner."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from openhands_cli.tui.core.conversation_runner import ConversationRunner


# ============================================================================
# persistence_dir Property Tests
# ============================================================================


class TestPersistenceDir:
    """Tests for ConversationRunner.persistence_dir property."""

    @pytest.fixture
    def mock_runner(self) -> Any:
        """Create a ConversationRunner with mocked conversation."""
        runner = object.__new__(ConversationRunner)
        runner.conversation = None  # type: ignore[assignment]
        return runner

    def test_returns_none_when_no_conversation(self, mock_runner: Any):
        """Verify persistence_dir returns None when conversation is None."""
        mock_runner.conversation = None
        assert mock_runner.persistence_dir is None

    def test_returns_none_when_no_state(self, mock_runner: Any):
        """Verify persistence_dir returns None when conversation.state is None."""
        mock_conversation = MagicMock()
        mock_conversation.state = None
        mock_runner.conversation = mock_conversation
        assert mock_runner.persistence_dir is None

    def test_returns_path_when_available(self, mock_runner: Any):
        """Verify persistence_dir returns correct path from conversation state."""
        expected_path = "/test/persistence/path"

        mock_state = MagicMock()
        mock_state.persistence_dir = expected_path
        mock_conversation = MagicMock()
        mock_conversation.state = mock_state
        mock_runner.conversation = mock_conversation

        assert mock_runner.persistence_dir == expected_path
