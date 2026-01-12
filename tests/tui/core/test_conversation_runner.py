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

    def test_raises_when_no_conversation(self, mock_runner: Any):
        """Verify persistence_dir raises when conversation is None."""
        mock_runner.conversation = None
        with pytest.raises(AttributeError):
            _ = mock_runner.persistence_dir

    def test_raises_when_no_state(self, mock_runner: Any):
        """Verify persistence_dir raises when conversation.state is None."""
        mock_conversation = MagicMock()
        mock_conversation.state = None
        mock_runner.conversation = mock_conversation
        with pytest.raises(AttributeError):
            _ = mock_runner.persistence_dir

    def test_raises_when_no_persistence_dir(self, mock_runner: Any):
        """Verify persistence_dir raises when persistence_dir is not set."""
        mock_state = MagicMock()
        mock_state.persistence_dir = None
        mock_conversation = MagicMock()
        mock_conversation.state = mock_state
        mock_runner.conversation = mock_conversation

        with pytest.raises(Exception, match="Conversation is not being persisted"):
            _ = mock_runner.persistence_dir

    def test_returns_path_when_available(self, mock_runner: Any):
        """Verify persistence_dir returns correct path from conversation state."""
        expected_path = "/test/persistence/path"

        mock_state = MagicMock()
        mock_state.persistence_dir = expected_path
        mock_conversation = MagicMock()
        mock_conversation.state = mock_state
        mock_runner.conversation = mock_conversation

        assert mock_runner.persistence_dir == expected_path
