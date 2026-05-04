"""Snapshot tests for History Search modal."""

import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Footer, Input, Static

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.modals.history_search import HistorySearchScreen


class TestHistorySearchSnapshots:
    """Snapshot tests for the HistorySearchScreen."""

    def test_history_search_modal_initial(self, snap_compare, mock_locations):
        """Snapshot test for history search modal with mock data."""

        # Setup mock history data
        from openhands_cli.locations import get_prompt_history_path

        history_file = Path(get_prompt_history_path())
        history_file.parent.mkdir(parents=True, exist_ok=True)

        test_data = [
            {"text": "find the bug in logic", "timestamp": "2026-05-01T10:00:00"},
            {"text": "refactor the code", "timestamp": "2026-05-02T11:00:00"},
            {"text": "debug the layout issues", "timestamp": "2026-05-03T12:00:00"},
            {
                "text": (
                    "a very long prompt that should be truncated in the preview "
                    "list but highlight perfectly when searched"
                ),
                "timestamp": "2026-05-04T13:00:00",
            },
        ]
        with open(history_file, "w") as f:
            json.dump(test_data, f)

        class HistorySearchTestApp(App):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_theme(OPENHANDS_THEME)
                self.theme = OPENHANDS_THEME.name

            def compose(self) -> ComposeResult:
                yield Static("Background content")
                yield Footer()

            def on_mount(self) -> None:
                self.push_screen(HistorySearchScreen())

        # Capture the initial state (all results shown, newest first)
        assert snap_compare(HistorySearchTestApp(), terminal_size=(100, 30))

    def test_history_search_modal_filtered(self, snap_compare, mock_locations):
        """Snapshot test for history search modal with a filter active."""

        # Setup mock history data
        from openhands_cli.locations import get_prompt_history_path

        history_file = Path(get_prompt_history_path())
        history_file.parent.mkdir(parents=True, exist_ok=True)

        test_data = [
            {"text": "find the bug in logic", "timestamp": "2026-05-01T10:00:00"},
            {"text": "refactor the code", "timestamp": "2026-05-02T11:00:00"},
            {"text": "debug the layout issues", "timestamp": "2026-05-03T12:00:00"},
        ]
        with open(history_file, "w") as f:
            json.dump(test_data, f)

        class HistorySearchFilteredApp(App):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_theme(OPENHANDS_THEME)
                self.theme = OPENHANDS_THEME.name

            def compose(self) -> ComposeResult:
                yield Static("Background content")
                yield Footer()

            async def on_mount(self) -> None:
                screen = HistorySearchScreen()
                await self.push_screen(screen)
                # Manually simulate typing a search term
                screen.query_one("#search_input", Input).value = "bug"

        # Capture the filtered state (highlights should be visible)
        assert snap_compare(HistorySearchFilteredApp(), terminal_size=(100, 30))
