import json
from pathlib import Path

import pytest
from textual.widgets import TextArea

from openhands_cli.tui.widgets.user_input.input_field import (
    InputField,
)


@pytest.mark.asyncio
async def test_hybrid_history_navigation(mock_locations):
    """Test automatic mode switching and boundary navigation in history."""
    # 1. Setup mixed history data (single and multi-line)
    from openhands_cli.locations import get_prompt_history_path

    history_file = Path(get_prompt_history_path())
    history_file.parent.mkdir(parents=True, exist_ok=True)

    test_data = [
        {"text": "single line 1", "timestamp": "2026-05-01T10:00:00"},
        {"text": "multi\nline\nprompt", "timestamp": "2026-05-02T11:00:00"},
        {"text": "single line 2", "timestamp": "2026-05-03T12:00:00"},
    ]
    with open(history_file, "w") as f:
        json.dump(test_data, f)

    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield InputField(id="input")

    app = TestApp()
    async with app.run_test() as pilot:
        input_field = app.query_one(InputField)
        await pilot.pause()

        # Initially in single-line mode
        assert not input_field.is_multiline_mode

        # --- Navigate Up ---

        # Up 1: should show 'single line 2'
        # Calling the handler directly ensures we test the logic,
        # avoiding event delivery issues
        input_field._handle_history_navigation("up")
        await pilot.pause()
        assert input_field.active_input_widget.text == "single line 2"
        assert not input_field.is_multiline_mode

        # Up 2: should show 'multi\\nline\\nprompt' and AUTO-SWITCH to multiline
        input_field._handle_history_navigation("up")
        await pilot.pause()
        assert input_field.active_input_widget.text == "multi\nline\nprompt"
        assert input_field.is_multiline_mode
        assert isinstance(input_field.active_input_widget, TextArea)

        # Up 3: Hitting Up again should navigate
        # (logic should ignore cursor line since we call handler directly)
        input_field._handle_history_navigation("up")
        await pilot.pause()
        assert input_field.active_input_widget.text == "single line 1"
        assert not input_field.is_multiline_mode  # AUTO-SWITCHED back to single

        # --- Navigate Down ---

        # Down 1: Back to multiline prompt
        input_field._handle_history_navigation("down")
        await pilot.pause()
        assert input_field.active_input_widget.text == "multi\nline\nprompt"
        assert input_field.is_multiline_mode

        # Down 2: Back to 'single line 2'
        input_field._handle_history_navigation("down")
        await pilot.pause()
        assert input_field.active_input_widget.text == "single line 2"
        assert not input_field.is_multiline_mode

        # Down 3: Back to empty bottom
        input_field._handle_history_navigation("down")
        await pilot.pause()
        assert input_field.active_input_widget.text == ""
        assert not input_field.is_multiline_mode


@pytest.mark.asyncio
async def test_multiline_wip_preservation(mock_locations):
    """Test that a multi-line WIP is preserved when navigating history."""
    from openhands_cli.locations import get_prompt_history_path

    history_file = Path(get_prompt_history_path())
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with open(history_file, "w") as f:
        json.dump([{"text": "old prompt", "timestamp": "2026-05-01T10:00:00"}], f)

    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield InputField(id="input")

    app = TestApp()
    async with app.run_test() as pilot:
        input_field = app.query_one(InputField)
        await pilot.pause()

        # 1. Type a multi-line WIP
        input_field.action_toggle_input_mode()
        await pilot.pause()
        input_field.active_input_widget.text = "my\nnew\nwip"
        assert input_field.is_multiline_mode

        # 2. Navigate Up into history
        input_field._handle_history_navigation("up")
        await pilot.pause()

        assert input_field.active_input_widget.text == "old prompt"
        assert (
            not input_field.is_multiline_mode
        )  # Collapsed because 'old prompt' is single line

        # 3. Navigate Down back to WIP
        input_field._handle_history_navigation("down")
        await pilot.pause()
        assert input_field.active_input_widget.text == "my\nnew\nwip"
        assert input_field.is_multiline_mode  # Re-expanded!
