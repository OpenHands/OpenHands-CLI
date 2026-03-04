"""Scale smoke tests and performance regression tests for adaptive replay (T06.02, T06.04).

Validates:
- Replay cascade operates correctly at 1K, 10K, and 60K event scales
- Widget count remains bounded by window_size (never materialises full history)
- Performance thresholds: 1K<50ms, 10K<100ms, 60K<500ms for _build_replay_plan
"""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from openhands.sdk.event.base import Event


def _make_events(n: int) -> list[Event]:
    """Create n lightweight mock events."""
    events = []
    for i in range(n):
        ev = MagicMock(spec=Event)
        ev.id = f"ev-{i}"
        ev.name = f"ev-{i}"
        events.append(ev)
    return events


def _build_runner(window_size: int = 200):
    """Build a ConversationRunner with mocked dependencies."""
    with patch(
        "openhands_cli.tui.core.conversation_runner.setup_conversation"
    ) as mock_setup:
        mock_conv = MagicMock()
        mock_conv.state.events = []
        mock_setup.return_value = mock_conv

        import uuid
        from openhands_cli.tui.core.conversation_runner import ConversationRunner

        visualizer = MagicMock()
        visualizer.cli_settings = SimpleNamespace(replay_window_size=window_size)

        runner = ConversationRunner(
            conversation_id=uuid.uuid4(),
            state=MagicMock(),
            message_pump=MagicMock(),
            notification_callback=MagicMock(),
            visualizer=visualizer,
        )
        runner.conversation = mock_conv
        return runner


# ============================================================================
# T06.02: Scale smoke tests
# ============================================================================


class TestReplayScaleSmoke:
    """Smoke tests at 1K/10K/60K event scales."""

    @pytest.mark.parametrize("scale", [1_000, 10_000, 60_000], ids=["1K", "10K", "60K"])
    def test_replay_at_scale_bounded_widget_count(self, scale: int):
        """Replay produces at most window_size events, regardless of total scale."""
        window = 200
        runner = _build_runner(window_size=window)
        events = _make_events(scale)
        runner.conversation.state.events = events

        count = runner.replay_historical_events()

        # Should replay exactly window_size events (since scale >> window)
        assert count == window
        # Visualizer should receive tail_events of length window
        runner.visualizer.replay_with_summary.assert_called_once()
        call_kwargs = runner.visualizer.replay_with_summary.call_args[1]
        assert len(call_kwargs["tail_events"]) == window
        assert call_kwargs["total_count"] == scale
        assert call_kwargs["hidden_count"] == scale - window

    @pytest.mark.parametrize("scale", [1_000, 10_000, 60_000], ids=["1K", "10K", "60K"])
    def test_replay_plan_is_deterministic_at_scale(self, scale: int):
        """Two consecutive plan builds produce identical results."""
        window = 200
        runner = _build_runner(window_size=window)
        events = _make_events(scale)

        plan1 = runner._build_replay_plan(events, total_count=scale)
        plan2 = runner._build_replay_plan(events, total_count=scale)

        assert plan1.total_count == plan2.total_count
        assert plan1.hidden_count == plan2.hidden_count
        assert len(plan1.tail_events) == len(plan2.tail_events)
        assert plan1.has_condensation == plan2.has_condensation


# ============================================================================
# T06.04: Graduated performance regression tests
# ============================================================================


class TestReplayPerformanceRegression:
    """Performance threshold enforcement for _build_replay_plan."""

    @pytest.mark.parametrize(
        "scale,max_ms",
        [(1_000, 50), (10_000, 100), (60_000, 500)],
        ids=["1K<50ms", "10K<100ms", "60K<500ms"],
    )
    def test_build_replay_plan_within_threshold(self, scale: int, max_ms: int):
        """_build_replay_plan completes within graduated thresholds."""
        runner = _build_runner(window_size=200)
        events = _make_events(scale)

        # Warm up
        runner._build_replay_plan(events, total_count=scale)

        # Measure
        t0 = time.monotonic()
        plan = runner._build_replay_plan(events, total_count=scale)
        elapsed_ms = (time.monotonic() - t0) * 1000

        assert elapsed_ms < max_ms, (
            f"_build_replay_plan at {scale} events took {elapsed_ms:.1f}ms "
            f"(threshold: {max_ms}ms)"
        )
        assert len(plan.tail_events) == 200
        assert plan.total_count == scale
