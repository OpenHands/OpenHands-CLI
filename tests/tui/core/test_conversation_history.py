"""Tests for conversation history state and pagination."""

from unittest.mock import MagicMock, Mock

from openhands_cli.tui.core.conversation_history import (
    DEFAULT_PAGE_SIZE,
    ConversationHistoryState,
    create_conversation_history_state,
    render_events_to_visualizer,
)


class TestConversationHistoryState:
    """Tests for ConversationHistoryState dataclass."""

    def test_empty_events(self):
        """Empty events list should have no more to render."""
        state = ConversationHistoryState(events=[], rendered_count=0)
        assert not state.has_more
        assert state.remaining_count == 0
        assert state.get_next_page() == []
        assert state.get_initial_page() == []

    def test_has_more_with_events(self):
        """Should report has_more when events exist."""
        events = [Mock() for _ in range(10)]
        state = ConversationHistoryState(events=events, rendered_count=0)
        assert state.has_more
        assert state.remaining_count == 10

    def test_has_more_after_partial_render(self):
        """Should report has_more after partial render."""
        events = [Mock() for _ in range(10)]
        state = ConversationHistoryState(events=events, rendered_count=5)
        assert state.has_more
        assert state.remaining_count == 5

    def test_no_more_when_all_rendered(self):
        """Should not have more when all events rendered."""
        events = [Mock() for _ in range(10)]
        state = ConversationHistoryState(events=events, rendered_count=10)
        assert not state.has_more
        assert state.remaining_count == 0

    def test_get_initial_page_returns_last_n_events(self):
        """Initial page should return the last N events."""
        events = [Mock(name=f"event_{i}") for i in range(10)]
        state = ConversationHistoryState(events=events, page_size=5)

        initial = state.get_initial_page()

        assert len(initial) == 5
        # Should be the last 5 events (indices 5-9)
        assert initial == events[5:10]
        assert state.rendered_count == 5

    def test_get_initial_page_with_fewer_events_than_page_size(self):
        """Initial page with fewer events than page size."""
        events = [Mock(name=f"event_{i}") for i in range(3)]
        state = ConversationHistoryState(events=events, page_size=5)

        initial = state.get_initial_page()

        assert len(initial) == 3
        assert initial == events
        assert state.rendered_count == 3

    def test_get_next_page_returns_older_events(self):
        """Next page should return older events."""
        events = [Mock(name=f"event_{i}") for i in range(10)]
        state = ConversationHistoryState(events=events, page_size=3)

        # Get initial page (last 3: indices 7, 8, 9)
        initial = state.get_initial_page()
        assert len(initial) == 3
        assert initial == events[7:10]

        # Get next page (indices 4, 5, 6)
        next_page = state.get_next_page()
        assert len(next_page) == 3
        assert next_page == events[4:7]

        # Get another page (indices 1, 2, 3)
        another_page = state.get_next_page()
        assert len(another_page) == 3
        assert another_page == events[1:4]

        # Get final page (index 0 only)
        final_page = state.get_next_page()
        assert len(final_page) == 1
        assert final_page == events[0:1]

        # No more pages
        assert not state.has_more
        assert state.get_next_page() == []

    def test_default_page_size(self):
        """Default page size should be DEFAULT_PAGE_SIZE."""
        events = [Mock() for _ in range(20)]
        state = ConversationHistoryState(events=events)

        assert state.page_size == DEFAULT_PAGE_SIZE
        initial = state.get_initial_page()
        assert len(initial) == DEFAULT_PAGE_SIZE


class TestCreateConversationHistoryState:
    """Tests for create_conversation_history_state factory function."""

    def test_creates_state_with_events(self):
        """Should create state with copied events."""
        events = [Mock() for _ in range(5)]
        state = create_conversation_history_state(events)

        assert len(state.events) == 5
        assert state.rendered_count == 0
        assert state.page_size == DEFAULT_PAGE_SIZE

    def test_creates_state_with_custom_page_size(self):
        """Should create state with custom page size."""
        events = [Mock() for _ in range(10)]
        state = create_conversation_history_state(events, page_size=3)

        assert state.page_size == 3

    def test_copies_events_list(self):
        """Should copy events list to avoid mutation."""
        events = [Mock() for _ in range(5)]
        state = create_conversation_history_state(events)

        # Mutate original list
        events.append(Mock())

        # State should not be affected
        assert len(state.events) == 5


class TestRenderEventsToVisualizer:
    """Tests for render_events_to_visualizer function."""

    def test_renders_all_events(self):
        """Should call on_event for each event."""
        events = [Mock() for _ in range(5)]
        visualizer = MagicMock()

        render_events_to_visualizer(events, visualizer)

        assert visualizer.on_event.call_count == 5
        for i, event in enumerate(events):
            visualizer.on_event.assert_any_call(event)

    def test_renders_in_order(self):
        """Should render events in chronological order."""
        events = [Mock(name=f"event_{i}") for i in range(3)]
        visualizer = MagicMock()
        call_order = []

        def track_call(event):
            call_order.append(event)

        visualizer.on_event.side_effect = track_call

        render_events_to_visualizer(events, visualizer)

        assert call_order == events

    def test_empty_events_no_calls(self):
        """Should not call on_event for empty list."""
        visualizer = MagicMock()

        render_events_to_visualizer([], visualizer)

        visualizer.on_event.assert_not_called()


class TestPaginationIntegration:
    """Integration tests for pagination workflow."""

    def test_full_pagination_workflow(self):
        """Test complete pagination from initial load to exhaustion."""
        # Create 12 events
        events = [Mock(name=f"event_{i}") for i in range(12)]
        state = create_conversation_history_state(events, page_size=5)

        # Initial load: last 5 events (indices 7-11)
        initial = state.get_initial_page()
        assert len(initial) == 5
        assert state.rendered_count == 5
        assert state.has_more

        # First "load more": events 2-6
        page1 = state.get_next_page()
        assert len(page1) == 5
        assert state.rendered_count == 10
        assert state.has_more

        # Second "load more": events 0-1
        page2 = state.get_next_page()
        assert len(page2) == 2
        assert state.rendered_count == 12
        assert not state.has_more

        # No more pages
        page3 = state.get_next_page()
        assert page3 == []

    def test_single_page_conversation(self):
        """Test conversation that fits in one page."""
        events = [Mock() for _ in range(3)]
        state = create_conversation_history_state(events, page_size=5)

        initial = state.get_initial_page()
        assert len(initial) == 3
        assert not state.has_more
        assert state.get_next_page() == []
