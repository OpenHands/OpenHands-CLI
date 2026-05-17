import json
from pathlib import Path

import pytest
from textual.widgets import OptionList

from openhands_cli.tui.modals.history_search import HistorySearchScreen


@pytest.mark.asyncio
async def test_history_search_flow(mock_locations):
    """Test the fuzzy search and selection flow in HistorySearchScreen."""
    # 1. Setup mock history data
    from openhands_cli.locations import get_prompt_history_path

    # We MUST use the actual location helper so the hash matches the code being tested
    history_file = Path(get_prompt_history_path())
    history_file.parent.mkdir(parents=True, exist_ok=True)

    test_data = [
        {"text": "find the bug in logic", "timestamp": "2026-05-01T10:00:00"},
        {"text": "refactor the code", "timestamp": "2026-05-02T11:00:00"},
        {"text": "debug the layout issues", "timestamp": "2026-05-03T12:00:00"},
    ]
    with open(history_file, "w") as f:
        json.dump(test_data, f)

    # 2. Launch the screen in a test app
    screen = HistorySearchScreen()

    from textual.app import App

    class TestApp(App):
        def __init__(self):
            super().__init__()
            self.search_result = "NOT_SET"

        def on_mount(self) -> None:
            def save_result(res: str | None):
                self.search_result = res

            self.push_screen(screen, save_result)

    app = TestApp()
    async with app.run_test() as pilot:
        # Wait for mount and initial results
        await pilot.pause()

        # Check initial state (should show all 3, newest first)
        option_list = screen.query_one("#results_list", OptionList)
        assert option_list.option_count == 3
        assert option_list.highlighted == 0

        # 3. Test Fuzzy Search
        # Type 'logic'
        await pilot.press(*"logic")
        await pilot.pause()

        assert option_list.option_count == 1
        # verify highlight is still at 0
        assert option_list.highlighted == 0

        # 4. Test Selection via Enter in Input
        # Press Enter while focused on input
        await pilot.press("enter")
        await pilot.pause()

        # The screen should dismiss and call our callback
        assert app.search_result == "find the bug in logic"
