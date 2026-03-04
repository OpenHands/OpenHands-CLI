"""Integration test: LoadOlderEvents full chain (T06.01).

Validates the message flow: ConversationManager → ConversationRunner → ConversationVisualizer
for the on-demand older-event loading feature.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import Static

from openhands.sdk import TextContent
from openhands.sdk.event import MessageEvent
from openhands.sdk.event.base import Event
from openhands_cli.tui.core.conversation_manager import ConversationManager
from openhands_cli.tui.core.events import LoadOlderEvents
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


def _make_mock_event(name: str) -> Event:
    ev = MagicMock(spec=Event, name=name)
    ev.id = name
    return ev


def _make_user_event(text: str) -> MessageEvent:
    ev = MagicMock(spec=MessageEvent)
    ev.llm_message = MagicMock()
    ev.llm_message.role = "user"
    ev.llm_message.content = [MagicMock(spec=TextContent, text=text)]
    ev.sender = None
    ev.__class__ = MessageEvent
    return ev


def _build_visualizer() -> ConversationVisualizer:
    """Build a minimal ConversationVisualizer for integration testing."""
    from textual.app import App
    import collections

    app = MagicMock(spec=App)
    vis = ConversationVisualizer.__new__(ConversationVisualizer)
    vis._container = MagicMock()
    vis._container.children = []
    vis._app = app
    vis._name = None
    vis._main_thread_id = 0
    vis._cli_settings = MagicMock(replay_window_size=2)
    vis._pending_actions = {}
    vis._all_events = []
    vis._loaded_start_index = 0
    vis._banner_widget = None
    vis._summary_text = None
    vis._has_condensation = False
    vis._condensed_count = None
    vis._prepend_in_progress = False
    vis._live_event_buffer = collections.deque()
    vis._max_viewable_widgets = 2000
    return vis


class TestIntegrationLoadOlderEvents:
    """End-to-end chain test: manager → runner → visualizer."""

    def test_full_chain_loads_older_events(self):
        """Complete chain: set context → initial replay → load older via runner."""
        vis = _build_visualizer()

        # Simulate 5 events, window=2
        events = [_make_user_event(f"msg-{i}") for i in range(5)]

        with patch(
            "openhands_cli.tui.core.conversation_runner.setup_conversation"
        ) as mock_setup:
            import uuid
            from openhands_cli.tui.core.conversation_runner import ConversationRunner

            mock_conv = MagicMock()
            mock_conv.state.events = events
            mock_setup.return_value = mock_conv

            runner = ConversationRunner(
                conversation_id=uuid.uuid4(),
                state=MagicMock(),
                message_pump=MagicMock(),
                notification_callback=MagicMock(),
                visualizer=vis,
            )
            runner.conversation = mock_conv

        # Initial replay should use window=2
        count = runner.replay_historical_events()
        assert count == 2

        # Visualizer context should be set with all 5 events
        assert vis._loaded_start_index == 3  # 5 - 2 = 3
        assert len(vis._all_events) == 5

        # Now simulate a banner widget for the prepend path
        banner = Static("banner", id="replay-summary-banner", classes="replay-summary")
        vis._banner_widget = banner
        vis._container.children = [banner]

        # Load older events via runner (same as manager._on_load_older_events)
        loaded = runner.load_older_events()

        # Should load page_size=2 older events (indices 1,2)
        assert loaded == 2
        assert vis._loaded_start_index == 1

    def test_manager_delegates_to_runner_which_loads(self):
        """ConversationManager._on_load_older_events → runner.load_older_events → visualizer."""
        manager = object.__new__(ConversationManager)
        mock_runner = MagicMock()
        mock_runner.load_older_events.return_value = 3
        registry = MagicMock()
        registry.current = mock_runner
        manager._runners = registry

        event = LoadOlderEvents()
        manager._on_load_older_events(event)

        mock_runner.load_older_events.assert_called_once_with()

    def test_cap_prevents_unbounded_loading(self):
        """Widget cap stops loading after limit is reached."""
        vis = _build_visualizer()
        vis._max_viewable_widgets = 3

        events = [_make_user_event(f"msg-{i}") for i in range(10)]
        vis.set_replay_context(
            all_events=events,
            loaded_start_index=8,
            summary_text=None,
            has_condensation=False,
            condensed_count=None,
        )

        banner = Static("banner", id="replay-summary-banner", classes="replay-summary")
        vis._banner_widget = banner
        # Simulate 3 children already at cap
        vis._container.children = [
            Static("a"), Static("b"), Static("c"),
        ]

        loaded = vis.load_older_events()
        assert loaded == 0  # At cap, nothing loads

    def test_load_returns_zero_when_all_loaded(self):
        """No more events to load returns zero."""
        vis = _build_visualizer()

        events = [_make_user_event("msg-0")]
        vis.set_replay_context(
            all_events=events,
            loaded_start_index=0,  # Already at beginning
            summary_text=None,
            has_condensation=False,
            condensed_count=None,
        )

        loaded = vis.load_older_events()
        assert loaded == 0
