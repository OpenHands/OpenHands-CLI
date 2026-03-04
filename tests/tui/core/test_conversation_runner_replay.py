"""Tests for ConversationRunner replay planning and replay_historical_events()."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from openhands.sdk.event.condenser import Condensation


class TestReplayHistoricalEvents:
    """Tests for replay_historical_events and replay plan behavior."""

    @pytest.fixture
    def runner(self):
        """Create a ConversationRunner with mocked dependencies."""
        with patch(
            "openhands_cli.tui.core.conversation_runner.setup_conversation"
        ) as mock_setup:
            mock_conversation = MagicMock()
            mock_conversation.state.events = []
            mock_setup.return_value = mock_conversation

            import uuid

            from openhands_cli.tui.core.conversation_runner import ConversationRunner

            visualizer = MagicMock()
            visualizer.cli_settings = SimpleNamespace(replay_window_size=200)

            r = ConversationRunner(
                conversation_id=uuid.uuid4(),
                state=MagicMock(),
                message_pump=MagicMock(),
                notification_callback=MagicMock(),
                visualizer=visualizer,
            )
            r.conversation = mock_conversation
            return r

    def test_replays_all_events_in_order(self, runner):
        """replay_historical_events routes non-condensed history through replay_events."""
        events = [MagicMock(name="ev1"), MagicMock(name="ev2"), MagicMock(name="ev3")]
        runner.conversation.state.events = events

        count = runner.replay_historical_events()

        assert count == 3
        runner.visualizer.set_replay_context.assert_called_once()
        runner.visualizer.replay_events.assert_called_once_with(events)
        runner.visualizer.replay_with_summary.assert_not_called()

    def test_empty_history_returns_zero(self, runner):
        """No-op for empty histories."""
        runner.conversation.state.events = []

        count = runner.replay_historical_events()

        assert count == 0
        runner.visualizer.replay_events.assert_not_called()
        runner.visualizer.replay_with_summary.assert_not_called()

    def test_idempotent_second_call_returns_zero(self, runner):
        """Second call does not duplicate replay after offset has been set."""
        events = [MagicMock(name="ev1")]
        runner.conversation.state.events = events

        first = runner.replay_historical_events()
        assert first == 1

        second = runner.replay_historical_events()
        assert second == 0
        assert runner.visualizer.replay_events.call_count == 1

    def test_offset_set_after_replay(self, runner):
        """Offset tracks how many events were replayed."""
        events = [MagicMock(name="ev1"), MagicMock(name="ev2")]
        runner.conversation.state.events = events

        runner.replay_historical_events()

        assert runner._replayed_event_offset == 2

    def test_condensation_path_uses_replay_with_summary(self, runner):
        """Latest valid condensation drives summary+tail replay path."""
        old_event = MagicMock(name="old")
        old_event.id = "old-1"

        condensation = Condensation(
            id="cond-1",
            llm_response_id="resp-1",
            forgotten_event_ids=["old-1"],
            summary="Condensed setup and planning",
        )

        tail_1 = MagicMock(name="tail1")
        tail_1.id = "tail-1"
        tail_2 = MagicMock(name="tail2")
        tail_2.id = "tail-2"

        events = [old_event, condensation, tail_1, tail_2]
        runner.conversation.state.events = events

        count = runner.replay_historical_events()

        assert count == 2
        runner.visualizer.replay_with_summary.assert_called_once_with(
            summary_text="Condensed setup and planning",
            tail_events=[tail_1, tail_2],
            total_count=4,
            hidden_count=2,
            has_condensation=True,
            condensed_count=1,
        )
        runner.visualizer.replay_events.assert_not_called()

    def test_condensation_failure_falls_back_safely(self, runner):
        """Errors in condensation planning fall through to window/full path."""
        events = [MagicMock(name="ev1"), MagicMock(name="ev2")]
        runner.conversation.state.events = events

        with patch.object(
            runner,
            "_build_condensation_plan",
            side_effect=RuntimeError("corrupt condensation"),
        ):
            count = runner.replay_historical_events()

        assert count == 2
        runner.visualizer.set_replay_context.assert_called_once()
        runner.visualizer.replay_events.assert_called_once_with(events)
        runner.visualizer.replay_with_summary.assert_not_called()

    def test_latest_condensation_is_selected(self, runner):
        """Most recent condensation event wins when multiple exist."""
        pre = MagicMock(name="pre")
        pre.id = "pre-1"

        first_cond = Condensation(
            id="cond-1",
            llm_response_id="resp-1",
            forgotten_event_ids=["pre-1"],
            summary="Old summary",
        )

        middle = MagicMock(name="middle")
        middle.id = "mid-1"

        second_cond = Condensation(
            id="cond-2",
            llm_response_id="resp-2",
            forgotten_event_ids=["mid-1"],
            summary="Latest summary",
        )

        tail = MagicMock(name="tail")
        tail.id = "tail-1"

        events = [pre, first_cond, middle, second_cond, tail]
        runner.conversation.state.events = events

        count = runner.replay_historical_events()

        assert count == 1
        runner.visualizer.replay_with_summary.assert_called_once_with(
            summary_text="Latest summary",
            tail_events=[tail],
            total_count=5,
            hidden_count=4,
            has_condensation=True,
            condensed_count=1,
        )

    def test_condensation_none_summary_uses_summary_path(self, runner):
        """Condensation with summary=None still uses condensation banner branch."""
        hidden = MagicMock(name="hidden")
        hidden.id = "hidden-1"

        cond = Condensation(
            id="cond-1",
            llm_response_id="resp-1",
            forgotten_event_ids=["hidden-1"],
            summary=None,
        )

        tail = MagicMock(name="tail")
        tail.id = "tail-1"

        events = [hidden, cond, tail]
        runner.conversation.state.events = events

        count = runner.replay_historical_events()

        assert count == 1
        runner.visualizer.replay_with_summary.assert_called_once_with(
            summary_text=None,
            tail_events=[tail],
            total_count=3,
            hidden_count=2,
            has_condensation=True,
            condensed_count=1,
        )

    def test_extract_tail_events_uses_deque_fallback_for_iterable(self, runner):
        """Iterator-only event logs use deque fallback without requiring slicing."""
        events = [MagicMock(name=f"ev{i}") for i in range(5)]

        tail = runner._extract_tail_events(iter(events), window_size=2)

        assert tail == events[-2:]

    def test_runner_forwards_load_older_events_to_visualizer(self, runner):
        """Runner delegates older-page loading to visualizer."""
        runner.visualizer.load_older_events.return_value = 7

        loaded = runner.load_older_events()

        assert loaded == 7
        runner.visualizer.load_older_events.assert_called_once_with()

    def test_condensation_scan_fallback_for_non_sequence(self, runner):
        """Non-sequence streams still select the latest condensation event."""
        pre = MagicMock(name="pre")
        pre.id = "pre-1"

        first_cond = Condensation(
            id="cond-1",
            llm_response_id="resp-1",
            forgotten_event_ids=["pre-1"],
            summary="Old summary",
        )

        mid = MagicMock(name="mid")
        mid.id = "mid-1"

        second_cond = Condensation(
            id="cond-2",
            llm_response_id="resp-2",
            forgotten_event_ids=["mid-1"],
            summary="Latest summary",
        )

        tail = MagicMock(name="tail")
        tail.id = "tail-1"

        stream = iter([pre, first_cond, mid, second_cond, tail])

        plan = runner._build_replay_plan(stream, total_count=5)

        assert plan.summary_text == "Latest summary"
        assert plan.tail_events == [tail]
        assert plan.has_condensation is True
        assert plan.condensed_count == 1

    def test_build_replay_plan_window_path_sets_hidden_count(self, runner):
        """Window path computes hidden_count deterministically."""
        runner.visualizer.cli_settings.replay_window_size = 3
        events = [MagicMock(name=f"ev{i}") for i in range(6)]

        plan = runner._build_replay_plan(events, total_count=len(events))

        assert plan.summary_text is None
        assert plan.tail_events == events[-3:]
        assert plan.total_count == 6
        assert plan.hidden_count == 3
        assert plan.has_condensation is False
        assert plan.condensed_count is None
        assert plan.loadable_events == events
        assert plan.loaded_start_index == 3


class TestReplayEdgeCaseBoundaries:
    """Edge-case boundary tests for replay cascade (T05.05)."""

    @pytest.fixture
    def runner(self):
        """Create a ConversationRunner with mocked dependencies."""
        with patch(
            "openhands_cli.tui.core.conversation_runner.setup_conversation"
        ) as mock_setup:
            mock_conversation = MagicMock()
            mock_conversation.state.events = []
            mock_setup.return_value = mock_conversation

            import uuid

            from openhands_cli.tui.core.conversation_runner import ConversationRunner

            visualizer = MagicMock()
            visualizer.cli_settings = SimpleNamespace(replay_window_size=200)

            r = ConversationRunner(
                conversation_id=uuid.uuid4(),
                state=MagicMock(),
                message_pump=MagicMock(),
                notification_callback=MagicMock(),
                visualizer=visualizer,
            )
            r.conversation = mock_conversation
            return r

    def test_window_size_one_returns_single_event(self, runner):
        """Window=1 should replay exactly the last event."""
        runner.visualizer.cli_settings.replay_window_size = 1
        events = [MagicMock(name=f"ev{i}") for i in range(5)]
        runner.conversation.state.events = events

        count = runner.replay_historical_events()

        assert count == 1
        runner.visualizer.replay_with_summary.assert_called_once()
        call_kwargs = runner.visualizer.replay_with_summary.call_args
        assert call_kwargs[1]["tail_events"] == [events[-1]]
        assert call_kwargs[1]["hidden_count"] == 4

    def test_window_larger_than_event_count_replays_all(self, runner):
        """Window > total events should replay everything with no hidden count."""
        runner.visualizer.cli_settings.replay_window_size = 500
        events = [MagicMock(name=f"ev{i}") for i in range(3)]
        runner.conversation.state.events = events

        count = runner.replay_historical_events()

        assert count == 3
        runner.visualizer.replay_events.assert_called_once_with(events)
        runner.visualizer.replay_with_summary.assert_not_called()

    def test_zero_events_returns_zero(self, runner):
        """Empty event list produces no replay at all."""
        runner.conversation.state.events = []

        count = runner.replay_historical_events()

        assert count == 0
        runner.visualizer.replay_events.assert_not_called()
        runner.visualizer.replay_with_summary.assert_not_called()
        runner.visualizer.set_replay_context.assert_not_called()

    def test_exact_window_size_replays_all(self, runner):
        """When total == window_size, all events replay with no hidden."""
        runner.visualizer.cli_settings.replay_window_size = 5
        events = [MagicMock(name=f"ev{i}") for i in range(5)]
        runner.conversation.state.events = events

        count = runner.replay_historical_events()

        assert count == 5
        runner.visualizer.replay_events.assert_called_once_with(events)
        runner.visualizer.replay_with_summary.assert_not_called()

    def test_single_event_with_default_window(self, runner):
        """Single event with default window produces full passthrough."""
        events = [MagicMock(name="only")]
        runner.conversation.state.events = events

        count = runner.replay_historical_events()

        assert count == 1
        runner.visualizer.replay_events.assert_called_once_with(events)
        runner.visualizer.replay_with_summary.assert_not_called()


class TestForgottenEventIdsFiltering:
    """Tests for forgotten_event_ids exclusion in _build_condensation_plan (T07.02)."""

    @pytest.fixture
    def runner(self):
        """Create a ConversationRunner with mocked dependencies."""
        with patch(
            "openhands_cli.tui.core.conversation_runner.setup_conversation"
        ) as mock_setup:
            mock_conversation = MagicMock()
            mock_conversation.state.events = []
            mock_setup.return_value = mock_conversation

            import uuid

            from openhands_cli.tui.core.conversation_runner import ConversationRunner

            visualizer = MagicMock()
            visualizer.cli_settings = SimpleNamespace(replay_window_size=200)

            r = ConversationRunner(
                conversation_id=uuid.uuid4(),
                state=MagicMock(),
                message_pump=MagicMock(),
                notification_callback=MagicMock(),
                visualizer=visualizer,
            )
            r.conversation = mock_conversation
            return r

class TestReplayIdempotenceWithEmptyTail:
    """Regression: replay guard must work even when tail_events is empty (v0.04b)."""

    @pytest.fixture
    def runner(self):
        """Create a ConversationRunner with mocked dependencies."""
        with patch(
            "openhands_cli.tui.core.conversation_runner.setup_conversation"
        ) as mock_setup:
            mock_conversation = MagicMock()
            mock_conversation.state.events = []
            mock_setup.return_value = mock_conversation

            import uuid

            from openhands_cli.tui.core.conversation_runner import ConversationRunner

            visualizer = MagicMock()
            visualizer.cli_settings = SimpleNamespace(replay_window_size=200)

            r = ConversationRunner(
                conversation_id=uuid.uuid4(),
                state=MagicMock(),
                message_pump=MagicMock(),
                notification_callback=MagicMock(),
                visualizer=visualizer,
            )
            r.conversation = mock_conversation
            return r

    def test_replay_idempotent_with_empty_tail_after_condensation(self, runner):
        """Calling replay twice when tail_events=[] must not duplicate banners."""
        condensation = Condensation(
            id="cond-1",
            llm_response_id="resp-1",
            forgotten_event_ids=[],
            summary="Condensed context",
        )
        runner.conversation.state.events = [condensation]

        count1 = runner.replay_historical_events()
        count2 = runner.replay_historical_events()

        assert count2 == 0, "Second replay call must be blocked by guard"
        assert runner.visualizer.replay_with_summary.call_count == 1, (
            "replay_with_summary must be called exactly once, not duplicated"
        )


class TestForgottenEventIdsFiltering:
    """Tests for forgotten_event_ids exclusion in _build_condensation_plan (T07.02)."""

    @pytest.fixture
    def runner(self):
        """Create a ConversationRunner with mocked dependencies."""
        with patch(
            "openhands_cli.tui.core.conversation_runner.setup_conversation"
        ) as mock_setup:
            mock_conversation = MagicMock()
            mock_conversation.state.events = []
            mock_setup.return_value = mock_conversation

            import uuid

            from openhands_cli.tui.core.conversation_runner import ConversationRunner

            visualizer = MagicMock()
            visualizer.cli_settings = SimpleNamespace(replay_window_size=200)

            r = ConversationRunner(
                conversation_id=uuid.uuid4(),
                state=MagicMock(),
                message_pump=MagicMock(),
                notification_callback=MagicMock(),
                visualizer=visualizer,
            )
            r.conversation = mock_conversation
            return r

    def test_forgotten_tail_event_excluded_from_plan(self, runner):
        """A tail event whose ID is in forgotten_event_ids is excluded from tail_events."""
        pre = MagicMock(name="pre")
        pre.id = "pre-1"

        condensation = Condensation(
            id="cond-1",
            llm_response_id="resp-1",
            forgotten_event_ids=["pre-1", "tail-forgotten"],
            summary="Summary text",
        )

        tail_ok = MagicMock(name="tail_ok")
        tail_ok.id = "tail-ok"

        tail_forgotten = MagicMock(name="tail_forgotten")
        tail_forgotten.id = "tail-forgotten"

        events = [pre, condensation, tail_ok, tail_forgotten]

        plan = runner._build_condensation_plan(events, total_count=4)

        assert plan is not None
        assert plan.tail_events == [tail_ok]
        assert plan.has_condensation is True
        assert plan.condensed_count == 2

    def test_forgotten_tail_event_excluded_iterator_path(self, runner):
        """Iterator path also excludes tail events in forgotten_event_ids."""
        pre = MagicMock(name="pre")
        pre.id = "pre-1"

        condensation = Condensation(
            id="cond-1",
            llm_response_id="resp-1",
            forgotten_event_ids=["pre-1", "tail-forgotten"],
            summary="Summary text",
        )

        tail_ok = MagicMock(name="tail_ok")
        tail_ok.id = "tail-ok"

        tail_forgotten = MagicMock(name="tail_forgotten")
        tail_forgotten.id = "tail-forgotten"

        stream = iter([pre, condensation, tail_ok, tail_forgotten])

        plan = runner._build_condensation_plan(stream, total_count=4)

        assert plan is not None
        assert plan.tail_events == [tail_ok]
        assert plan.condensed_count == 2
