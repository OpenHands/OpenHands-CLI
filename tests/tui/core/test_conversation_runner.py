"""Tests for ConversationRunner."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
import uuid

import pytest

from openhands_cli.tui.core.conversation_runner import ConversationRunner


# ============================================================================
# ConversationRunner Basic Tests
# ============================================================================


class TestConversationRunnerBasics:
    """Basic tests for ConversationRunner functionality."""

    def test_is_confirmation_mode_active_default(self):
        """Verify confirmation mode is active by default (with AlwaysConfirm policy)."""
        with patch("openhands_cli.tui.core.conversation_runner.setup_conversation"):
            runner = ConversationRunner(
                conversation_id=uuid.uuid4(),
                running_state_callback=MagicMock(),
                confirmation_callback=MagicMock(),
                notification_callback=MagicMock(),
                visualizer=MagicMock(),
            )
            assert runner.is_confirmation_mode_active is True

    def test_is_running_initially_false(self):
        """Verify conversation is not running initially."""
        with patch("openhands_cli.tui.core.conversation_runner.setup_conversation"):
            runner = ConversationRunner(
                conversation_id=uuid.uuid4(),
                running_state_callback=MagicMock(),
                confirmation_callback=MagicMock(),
                notification_callback=MagicMock(),
                visualizer=MagicMock(),
            )
            assert runner.is_running is False
