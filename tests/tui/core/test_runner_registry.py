"""Tests for RunnerRegistry — replay integration."""

import uuid
from unittest.mock import MagicMock

import pytest

from openhands_cli.tui.core.runner_registry import RunnerRegistry


class TestRunnerRegistryReplay:
    """Tests that RunnerRegistry calls replay exactly once on new runner creation."""

    @pytest.fixture
    def mock_factory(self):
        factory = MagicMock()
        runner = MagicMock()
        runner.conversation = MagicMock()
        factory.create.return_value = runner
        return factory

    @pytest.fixture
    def registry(self, mock_factory):
        return RunnerRegistry(
            factory=mock_factory,
            state=MagicMock(),
            message_pump=MagicMock(),
            notification_callback=MagicMock(),
        )

    def test_replay_called_on_new_runner(self, registry, mock_factory):
        """replay_historical_events is called once when a new runner is created."""
        cid = uuid.uuid4()
        runner = registry.get_or_create(cid)

        runner.replay_historical_events.assert_called_once()

    def test_replay_not_called_on_cached_runner(self, registry, mock_factory):
        """replay_historical_events is NOT called when fetching a cached runner."""
        cid = uuid.uuid4()
        runner = registry.get_or_create(cid)
        runner.replay_historical_events.reset_mock()

        # Second call should return cached runner without replaying
        same_runner = registry.get_or_create(cid)
        assert same_runner is runner
        runner.replay_historical_events.assert_not_called()

    def test_replay_called_per_conversation(self, registry, mock_factory):
        """Each new conversation gets its own replay call."""
        cid_a = uuid.uuid4()
        cid_b = uuid.uuid4()

        # Create distinct mock runners for each conversation
        runner_a = MagicMock()
        runner_a.conversation = MagicMock()
        runner_b = MagicMock()
        runner_b.conversation = MagicMock()
        mock_factory.create.side_effect = [runner_a, runner_b]

        registry.get_or_create(cid_a)
        registry.get_or_create(cid_b)

        runner_a.replay_historical_events.assert_called_once()
        runner_b.replay_historical_events.assert_called_once()

    def test_replay_failure_leaves_cache_empty(self, registry, mock_factory):
        """If replay_historical_events raises, the runner must NOT be cached."""
        cid = uuid.uuid4()
        runner = mock_factory.create.return_value
        runner.replay_historical_events.side_effect = RuntimeError("replay failed")

        with pytest.raises(RuntimeError, match="replay failed"):
            registry.get_or_create(cid)

        assert cid not in registry._runners

    def test_replay_failure_propagates_exception(self, registry, mock_factory):
        """The exception from replay_historical_events must propagate to the caller."""
        cid = uuid.uuid4()
        runner = mock_factory.create.return_value
        runner.replay_historical_events.side_effect = ValueError("bad event")

        with pytest.raises(ValueError, match="bad event"):
            registry.get_or_create(cid)
