"""Tests for ConversationVisualizer replay rendering behavior."""

from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.widgets import Static

from openhands.sdk import MessageEvent, TextContent
from openhands.sdk.event import ObservationEvent
from openhands.sdk.event.base import Event
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_container():
    """Create a mock container that supports mount and scroll_end."""
    container = MagicMock()
    container.is_vertical_scroll_end = False
    return container


@pytest.fixture
def visualizer(mock_container):
    """Create a ConversationVisualizer with mock app and mock container."""
    app = MagicMock(spec=App)
    vis = ConversationVisualizer.__new__(ConversationVisualizer)
    # Manually initialize required attributes to avoid full Textual init
    vis._container = mock_container
    vis._app = app
    vis._name = None
    vis._main_thread_id = 0  # Will not match, but replay_events doesn't check
    vis._cli_settings = MagicMock(replay_window_size=2)
    vis._pending_actions = {}
    vis._all_events = []
    vis._loaded_start_index = 0
    vis._banner_widget = None
    vis._summary_text = None
    vis._has_condensation = False
    vis._condensed_count = None
    vis._prepend_in_progress = False
    vis._live_event_buffer = __import__("collections").deque()
    vis._max_viewable_widgets = 2000
    return vis


def _make_user_message_event(text: str) -> MessageEvent:
    """Create a MessageEvent representing a user message."""
    event = MagicMock(spec=MessageEvent)
    event.llm_message = MagicMock()
    event.llm_message.role = "user"
    event.llm_message.content = [MagicMock(spec=TextContent, text=text)]
    event.sender = None
    # Ensure isinstance checks work
    event.__class__ = MessageEvent
    return event


def _make_observation_event(tool_call_id: str = "tc-1") -> ObservationEvent:
    """Create a mock ObservationEvent."""
    event = MagicMock(spec=ObservationEvent)
    event.tool_call_id = tool_call_id
    event.__class__ = ObservationEvent
    return event


# ============================================================================
# T-1: Single user message produces one Static widget
# ============================================================================


class TestReplayRendering:
    """Core rendering tests for replay_events()."""

    def test_single_user_message_produces_static_widget(self, visualizer, mock_container):
        """T-1: A single user message event produces one Static widget with
        CSS class 'user-message' and correct text content."""
        event = _make_user_message_event("Hello world")

        visualizer.replay_events([event])

        assert mock_container.mount.call_count == 1
        widget = mock_container.mount.call_args[0][0]
        assert isinstance(widget, Static)
        assert "user-message" in widget.classes
        assert "Hello world" in str(widget._Static__content)

    def test_observation_event_routes_through_handler(self, visualizer, mock_container):
        """T-2: Observation events route through _handle_observation_event.
        Widget order matches event order."""
        user_event = _make_user_message_event("test input")
        obs_event = _make_observation_event("tc-1")

        with patch.object(
            visualizer, "_handle_observation_event", return_value=True
        ) as mock_handler:
            visualizer.replay_events([user_event, obs_event])

        # User message should produce a mounted widget
        assert mock_container.mount.call_count == 1
        # Observation should have been routed to handler
        mock_handler.assert_called_once_with(obs_event)

    def test_multiple_pairs_render_in_order(self, visualizer, mock_container):
        """T-3: Multiple user/observation pairs render in correct order;
        widget count matches expected."""
        events = [
            _make_user_message_event("first message"),
            _make_observation_event("tc-1"),
            _make_user_message_event("second message"),
            _make_observation_event("tc-2"),
        ]

        with patch.object(
            visualizer, "_handle_observation_event", return_value=True
        ):
            visualizer.replay_events(events)

        # Two user messages should produce two mounted widgets
        assert mock_container.mount.call_count == 2
        # Verify ordering
        first_widget = mock_container.mount.call_args_list[0][0][0]
        second_widget = mock_container.mount.call_args_list[1][0][0]
        assert "first message" in str(first_widget._Static__content)
        assert "second message" in str(second_widget._Static__content)


# ============================================================================
# T-4: Scroll behavior — scroll_end called once after all events
# ============================================================================


class TestReplayScrollBehavior:
    """Scroll behavior tests for replay_events()."""

    def test_scroll_end_called_once_after_all_events(self, visualizer, mock_container):
        """T-4: scroll_end(animate=False) is called exactly once after all events."""
        events = [
            _make_user_message_event("msg 1"),
            _make_user_message_event("msg 2"),
            _make_user_message_event("msg 3"),
        ]

        visualizer.replay_events(events)

        mock_container.scroll_end.assert_called_once_with(animate=False)


class TestReplayWithSummary:
    """Tests for replay_with_summary banner + tail behavior."""

    def _make_tail_event(self, text: str) -> Event:
        return _make_user_message_event(text)

    def test_replay_with_summary_renders_collapsible_banner(self, visualizer, mock_container):
        tail = [self._make_tail_event("tail event")]

        visualizer.replay_with_summary(
            summary_text="Earlier context summary",
            tail_events=tail,
            total_count=10,
            hidden_count=9,
            has_condensation=True,
            condensed_count=7,
        )

        # Banner + one tail widget are mounted
        assert mock_container.mount.call_count == 2
        banner = mock_container.mount.call_args_list[0][0][0]
        assert "replay-summary" in banner.classes
        assert banner.id == "replay-summary-banner"
        assert "Prior context: 7 events condensed" in str(banner.title)

    def test_replay_with_summary_renders_count_banner_without_summary(
        self, visualizer, mock_container
    ):
        tail = [self._make_tail_event("tail")]

        visualizer.replay_with_summary(
            summary_text=None,
            tail_events=tail,
            total_count=10,
            hidden_count=9,
            has_condensation=False,
            condensed_count=None,
        )

        assert mock_container.mount.call_count == 2
        banner = mock_container.mount.call_args_list[0][0][0]
        assert isinstance(banner, Static)
        assert "9 earlier events not shown" in str(banner._Static__content)
        assert "replay-summary" in banner.classes
        assert banner.id == "replay-summary-banner"

    def test_replay_with_summary_no_hidden_count_means_no_banner(
        self, visualizer, mock_container
    ):
        tail = [self._make_tail_event("only")]

        visualizer.replay_with_summary(
            summary_text="ignored",
            tail_events=tail,
            total_count=1,
            hidden_count=0,
            has_condensation=True,
            condensed_count=1,
        )

        assert mock_container.mount.call_count == 1

    def test_replay_with_summary_condensation_none_uses_fallback_static(
        self, visualizer, mock_container
    ):
        tail = [self._make_tail_event("tail")]

        visualizer.replay_with_summary(
            summary_text=None,
            tail_events=tail,
            total_count=10,
            hidden_count=9,
            has_condensation=True,
            condensed_count=7,
        )

        assert mock_container.mount.call_count == 2
        banner = mock_container.mount.call_args_list[0][0][0]
        assert isinstance(banner, Static)
        assert "Prior context condensed (7 events). Summary not available." in str(
            banner._Static__content
        )


# ============================================================================
# T-5: Empty event list edge case
# ============================================================================


class TestLoadOlderEvents:
    """Tests for prepend loading behavior."""

    def test_load_older_events_prepends_before_banner(self, visualizer, mock_container):
        e1 = _make_user_message_event("older-1")
        e2 = _make_user_message_event("older-2")
        e3 = _make_user_message_event("tail-1")

        banner = Static("banner", id="replay-summary-banner", classes="replay-summary")
        mock_container.children = [banner]

        visualizer.set_replay_context(
            all_events=[e1, e2, e3],
            loaded_start_index=2,
            summary_text=None,
            has_condensation=False,
            condensed_count=None,
        )
        visualizer._banner_widget = banner

        loaded = visualizer.load_older_events()

        assert loaded == 2
        assert visualizer._loaded_start_index == 0
        mount_calls = mock_container.mount.call_args_list[:2]
        assert len(mount_calls) == 2
        assert all(call.kwargs.get("before") is banner for call in mount_calls)

    def test_load_older_events_cap_stops_loading(self, visualizer, mock_container):
        visualizer._max_viewable_widgets = 1
        mock_container.children = [Static("existing")]

        visualizer.set_replay_context(
            all_events=[_make_user_message_event("older")],
            loaded_start_index=1,
            summary_text=None,
            has_condensation=False,
            condensed_count=None,
        )

        loaded = visualizer.load_older_events()

        assert loaded == 0

    def test_on_event_buffers_while_prepend_in_progress(self, visualizer):
        live = _make_user_message_event("live")
        visualizer._prepend_in_progress = True

        visualizer.on_event(live)

        assert len(visualizer._live_event_buffer) == 1

    def test_update_banner_to_terminal_message_on_cap(self, visualizer, mock_container):
        banner = Static("banner", id="replay-summary-banner", classes="replay-summary")
        mock_container.children = [banner]
        visualizer._banner_widget = banner
        visualizer._loaded_start_index = 10
        visualizer._max_viewable_widgets = 1
        mock_container.children = [banner, Static("one")]

        visualizer._update_banner_for_loaded_state()

        assert isinstance(visualizer._banner_widget, Static)
        assert "Maximum viewable history reached." in str(visualizer._banner_widget._Static__content)


class TestReplayEdgeCases:
    """Edge case tests for replay_events()."""

    def test_empty_event_list_produces_no_widgets(self, visualizer, mock_container):
        """T-5: An empty event list produces no widgets and no exception."""
        visualizer.replay_events([])

        mock_container.mount.assert_not_called()
        # Per implementation: scroll_end is NOT called when events list is empty
        # (the `if events:` guard skips it)
        mock_container.scroll_end.assert_not_called()

    def test_cross_boundary_observation_gets_indicator(self, visualizer, mock_container):
        """Observation without matching action in window shows '(action not shown)'."""
        obs = _make_observation_event("tc-orphan")
        # Ensure _handle_observation_event returns False (no match)
        with patch.object(
            visualizer, "_handle_observation_event", return_value=False
        ), patch.object(
            visualizer,
            "_create_cross_boundary_observation_widget",
            return_value=Static("(action not shown) Obs"),
        ) as mock_cross:
            visualizer.replay_events([obs])

        mock_cross.assert_called_once_with(obs)


# ============================================================================
# T-6, T-7, T-8: Side-effect omission regression guards
# ============================================================================


class TestReplaySideEffectOmissions:
    """Regression guards verifying that replay_events() intentionally omits
    certain side effects that on_event() performs.

    These are negative assertions — they document that the omissions are
    intentional design decisions, not bugs.
    """

    def test_critic_event_not_triggered_during_replay(self, visualizer, mock_container):
        """T-6: Critic handling is intentionally omitted during replay.

        Replay renders historical events for visual display only. Critic
        evaluation is a live-session concern — replaying events should
        never trigger critic analysis of already-completed work.
        """
        events = [_make_user_message_event("please review this")]

        with patch.object(
            visualizer, "_handle_observation_event", return_value=False
        ):
            visualizer.replay_events(events)

        # Verify no critic-related attributes or methods were invoked.
        # The replay code path has no critic references by design.
        # This test guards against future changes that accidentally add them.
        for call in mock_container.method_calls:
            assert "critic" not in str(call).lower(), (
                "Critic side effect detected during replay — intentionally omitted"
            )

    def test_telemetry_not_triggered_during_replay(self, visualizer, mock_container):
        """T-7: Telemetry calls are intentionally omitted during replay.

        Replaying historical events must not re-emit telemetry for events
        that were already tracked during the original session. This prevents
        double-counting and incorrect metrics.
        """
        events = [_make_user_message_event("tracked message")]

        with patch(
            "openhands_cli.tui.widgets.richlog_visualizer.posthog",
            create=True,
        ) as mock_posthog:
            visualizer.replay_events(events)

        # posthog should not be called during replay
        if hasattr(mock_posthog, "capture"):
            mock_posthog.capture.assert_not_called()

    def test_plan_panel_not_refreshed_during_replay(self, visualizer, mock_container):
        """T-8: Plan panel refresh is intentionally omitted during replay.

        During live sessions, certain events trigger plan panel updates.
        During replay, the plan panel state is reconstructed separately —
        replay_events() must not trigger incremental plan panel refreshes.
        """
        events = [_make_user_message_event("create a plan")]

        visualizer.replay_events(events)

        # Verify no plan-panel-related calls on the app or container
        for call in mock_container.method_calls:
            assert "plan" not in str(call).lower(), (
                "Plan panel side effect detected during replay — intentionally omitted"
            )


# ============================================================================
# T07.03: Cross-boundary observation widget content test
# ============================================================================


class TestCrossBoundaryObservationWidgetContent:
    """Test that _create_cross_boundary_observation_widget() produces correct content."""

    def test_widget_title_contains_action_not_shown(self, visualizer):
        """Real method call produces title with '(action not shown)' prefix (T07.03)."""
        obs = _make_observation_event("tc-orphan")
        obs.visualize = "Some observation output"

        widget = visualizer._create_cross_boundary_observation_widget(obs)

        assert widget is not None
        assert "(action not shown)" in str(widget.title)


# ============================================================================
# T07.05: _flush_live_event_buffer drain test
# ============================================================================


class TestFlushLiveEventBuffer:
    """Test that _flush_live_event_buffer drains buffer and re-dispatches via on_event."""

    def test_flush_drains_buffer_and_redispatches(self, visualizer):
        """Buffered events are re-dispatched via on_event after flush (T07.05)."""
        live_event = _make_user_message_event("live during prepend")

        # Simulate buffering during prepend
        visualizer._prepend_in_progress = True
        visualizer.on_event(live_event)
        assert len(visualizer._live_event_buffer) == 1

        # End prepend and flush
        visualizer._prepend_in_progress = False

        with patch.object(visualizer, "on_event") as mock_on_event:
            visualizer._flush_live_event_buffer()

        assert len(visualizer._live_event_buffer) == 0
        mock_on_event.assert_called_once_with(live_event)


# ============================================================================
# v0.04b Regression: _loaded_start_index consumed-vs-mounted tracking
# ============================================================================


class TestLoadOlderEventsConsumedTracking:
    """Regression tests for _loaded_start_index decrement using consumed counter."""

    def test_load_older_advances_index_when_events_filtered(self, visualizer, mock_container):
        """_loaded_start_index must advance by consumed count, not mounted count."""
        e1 = _make_user_message_event("older-1")
        e2 = MagicMock(spec=Event)  # Will produce None widget
        e3 = _make_user_message_event("older-3")

        # Set page size large enough to load all 3 events in one page
        visualizer._cli_settings.replay_window_size = 10

        visualizer.set_replay_context(
            all_events=[e1, e2, e3],
            loaded_start_index=3,
            summary_text=None,
            has_condensation=False,
            condensed_count=None,
        )
        # Start with empty children so _visible_widget_count returns 0
        mock_container.children = []

        def create_with_filter(event):
            if event is e2:
                return None
            return Static(f"widget-{id(event)}")

        with patch.object(visualizer, "_create_replay_widget", side_effect=create_with_filter):
            mounted = visualizer.load_older_events()

        # consumed=3 (all 3 events processed), mounted=2 (e2 filtered)
        assert visualizer._loaded_start_index == 0, (
            f"Expected 0 (3 - 3 consumed), got {visualizer._loaded_start_index}"
        )
        assert mounted == 2, f"Expected 2 mounted widgets, got {mounted}"

    def test_load_older_cap_break_limits_consumed(self, visualizer, mock_container):
        """When _max_viewable_widgets cap breaks loop, consumed != len(older_events)."""
        e1 = _make_user_message_event("older-1")
        e2 = _make_user_message_event("older-2")
        e3 = _make_user_message_event("older-3")

        visualizer.set_replay_context(
            all_events=[e1, e2, e3],
            loaded_start_index=3,
            summary_text=None,
            has_condensation=False,
            condensed_count=None,
        )
        visualizer._max_viewable_widgets = 1
        # Start empty so first _visible_widget_count() returns 0, then after mount returns 1
        widget_count = [0]

        def mock_visible_count():
            return widget_count[0]

        def create_and_count(event):
            w = Static(f"widget-{id(event)}")
            return w

        original_mount = mock_container.mount

        def mount_and_track(*args, **kwargs):
            original_mount(*args, **kwargs)
            widget_count[0] += 1

        mock_container.mount = MagicMock(side_effect=mount_and_track)
        mock_container.children = []

        with (
            patch.object(visualizer, "_visible_widget_count", side_effect=mock_visible_count),
            patch.object(visualizer, "_create_replay_widget", side_effect=create_and_count),
        ):
            mounted = visualizer.load_older_events()

        # First iteration: visible=0 < max=1, consumed=1, mount → visible=1
        # Second iteration: visible=1 >= max=1 → break
        assert visualizer._loaded_start_index == 2, (
            f"Expected 2 (3 - 1 consumed), got {visualizer._loaded_start_index}"
        )
        assert mounted == 1, f"Expected 1 mounted widget, got {mounted}"
