"""Tests for switch conversation confirmation modal functionality."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from openhands_cli.tui.modals.switch_conversation_modal import SwitchConversationModal


class SwitchModalTestApp(App):
    """App for testing SwitchConversationModal."""

    def compose(self) -> ComposeResult:
        yield Static("main")


@pytest.mark.asyncio
async def test_switch_modal_focuses_non_destructive_button_on_mount() -> None:
    """The modal should focus the non-destructive action first."""
    app = SwitchModalTestApp()
    async with app.run_test() as pilot:
        modal = SwitchConversationModal(prompt="Switch?")
        pilot.app.push_screen(modal)
        await pilot.pause()

        no_button = modal.query_one("#no", Button)
        assert pilot.app.focused == no_button


@pytest.mark.asyncio
async def test_switch_modal_arrow_keys_move_focus_between_choices() -> None:
    """Left and right arrows should move focus between the two buttons."""
    app = SwitchModalTestApp()
    async with app.run_test() as pilot:
        modal = SwitchConversationModal(prompt="Switch?")
        pilot.app.push_screen(modal)
        await pilot.pause()

        yes_button = modal.query_one("#yes", Button)
        no_button = modal.query_one("#no", Button)
        assert pilot.app.focused == no_button

        await pilot.press("left")
        assert pilot.app.focused == yes_button

        await pilot.press("right")
        assert pilot.app.focused == no_button


@pytest.mark.asyncio
async def test_switch_modal_escape_returns_false() -> None:
    """Escape should dismiss the modal through the non-destructive path."""
    app = SwitchModalTestApp()
    async with app.run_test() as pilot:
        modal = SwitchConversationModal(prompt="Switch?")

        result: list[bool | None] = []
        pilot.app.push_screen(modal, result.append)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert result == [False]
