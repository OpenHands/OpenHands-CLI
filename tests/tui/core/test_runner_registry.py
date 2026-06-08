"""Tests for RunnerRegistry."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from openhands_cli.tui.core.runner_registry import RunnerRegistry


if TYPE_CHECKING:
    from openhands_cli.tui.core.conversation_runner import ConversationRunner


def _make_mock_runner() -> "ConversationRunner":
    """Create a new mock runner."""
    mock_runner = MagicMock()
    mock_runner.conversation = None  # Avoid attach_conversation_state call
    return mock_runner


class TestRunnerRegistry:
    """Tests for the RunnerRegistry class."""

    def _create_registry(self) -> RunnerRegistry:
        """Create a RunnerRegistry with mock dependencies."""
        factory = MagicMock()
        state = MagicMock()
        message_pump = MagicMock()
        notification_callback = MagicMock()

        # Configure factory.create to return a new mock runner each time
        factory.create.side_effect = lambda *args, **kwargs: _make_mock_runner()

        return RunnerRegistry(
            factory=factory,
            state=state,
            message_pump=message_pump,
            notification_callback=notification_callback,
        )

    def test_remove_nonexistent_runner_is_noop(self) -> None:
        """Removing a non-existent runner should not raise."""
        registry = self._create_registry()
        conversation_id = uuid.uuid4()

        # Should not raise
        registry.remove(conversation_id)

    def test_remove_existing_runner_clears_current(self) -> None:
        """Removing the current runner should clear the current reference."""
        registry = self._create_registry()
        conversation_id = uuid.uuid4()

        # Create a runner
        runner = registry.get_or_create(conversation_id)
        assert registry.current is runner

        # Remove it
        registry.remove(conversation_id)

        # Current should be cleared since removed runner was current
        assert registry.current is None

    def test_remove_creates_new_runner_on_next_get(self) -> None:
        """After removal, get_or_create should create a new runner."""
        registry = self._create_registry()
        conversation_id = uuid.uuid4()

        # Create a runner
        runner = registry.get_or_create(conversation_id)

        # Remove it
        registry.remove(conversation_id)

        # Getting the same conversation ID should create a new runner
        new_runner = registry.get_or_create(conversation_id)
        assert new_runner is not runner  # It's a new mock from factory

    def test_remove_non_current_runner_preserves_current(self) -> None:
        """Removing a non-current runner should not affect current."""
        registry = self._create_registry()
        conversation_id_1 = uuid.uuid4()
        conversation_id_2 = uuid.uuid4()

        # Create two runners
        runner_1 = registry.get_or_create(conversation_id_1)
        runner_2 = registry.get_or_create(conversation_id_2)

        # Current should be runner_2 (last get_or_create)
        assert registry.current is runner_2

        # Remove runner_1 (not current)
        registry.remove(conversation_id_1)

        # Current should still be runner_2
        assert registry.current is runner_2
