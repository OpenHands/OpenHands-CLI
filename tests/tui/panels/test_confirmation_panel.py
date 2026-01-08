"""Tests for inline confirmation panel functionality."""

from __future__ import annotations

from unittest import mock

import pytest
from textual.app import App
from textual.containers import Vertical
from textual.widgets import ListView, Static

from openhands_cli.tui.panels.confirmation_panel import InlineConfirmationPanel
from openhands_cli.user_actions.types import UserConfirmation


@pytest.fixture
def callback() -> mock.MagicMock:
    return mock.MagicMock()


def make_test_app(widget):
    class TestApp(App):
        def compose(self):
            yield widget

    return TestApp()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query, expected_type",
    [
        (".inline-confirmation-header", Static),
        (".inline-confirmation-content", Vertical),
    ],
)
async def test_inline_confirmation_panel_structure_contains_expected_nodes(
    callback: mock.MagicMock,
    query: str,
    expected_type: type,
):
    panel = InlineConfirmationPanel(
        num_actions=1,
        confirmation_callback=callback,
    )
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        nodes = pilot.app.query(query)
        assert len(nodes) == 1
        assert isinstance(nodes[0], expected_type)


@pytest.mark.asyncio
async def test_inline_confirmation_panel_has_listview(callback: mock.MagicMock):
    panel = InlineConfirmationPanel(
        num_actions=1,
        confirmation_callback=callback,
    )
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        assert (
            pilot.app.query_one("#inline-confirmation-listview", ListView) is not None
        )


@pytest.mark.parametrize(
    "item_id, expected_confirmation",
    [
        ("accept", UserConfirmation.ACCEPT),
        ("reject", UserConfirmation.REJECT),
        ("always", UserConfirmation.ALWAYS_PROCEED),
        ("risky", UserConfirmation.CONFIRM_RISKY),
    ],
)
def test_listview_selection_triggers_expected_callback(
    callback: mock.MagicMock,
    item_id: str,
    expected_confirmation: UserConfirmation,
):
    panel = InlineConfirmationPanel(
        num_actions=1,
        confirmation_callback=callback,
    )

    mock_item = mock.MagicMock()
    mock_item.id = item_id
    mock_event = mock.MagicMock()
    mock_event.item = mock_item

    panel.on_list_view_selected(mock_event)

    callback.assert_called_once_with(expected_confirmation)


@pytest.mark.asyncio
@pytest.mark.parametrize("num_actions", [1, 3, 5])
async def test_inline_panel_displays_correct_action_count(
    callback: mock.MagicMock, num_actions: int
):
    panel = InlineConfirmationPanel(
        num_actions=num_actions,
        confirmation_callback=callback,
    )
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        # Verify the panel was created with the correct num_actions
        inline_panel = pilot.app.query_one(InlineConfirmationPanel)
        assert inline_panel.num_actions == num_actions


@pytest.mark.asyncio
async def test_inline_panel_renders_and_listview_exists(callback: mock.MagicMock):
    panel = InlineConfirmationPanel(
        num_actions=2,
        confirmation_callback=callback,
    )
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        assert pilot.app.query_one(InlineConfirmationPanel) is not None
        assert (
            pilot.app.query_one("#inline-confirmation-listview", ListView) is not None
        )


@pytest.mark.asyncio
async def test_listview_is_focusable(callback: mock.MagicMock):
    panel = InlineConfirmationPanel(
        num_actions=1,
        confirmation_callback=callback,
    )
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        listview = pilot.app.query_one("#inline-confirmation-listview", ListView)
        assert listview.can_focus


@pytest.mark.asyncio
async def test_keyboard_enter_selects_first_item_and_calls_callback(
    callback: mock.MagicMock,
):
    panel = InlineConfirmationPanel(
        num_actions=1,
        confirmation_callback=callback,
    )
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        listview = pilot.app.query_one("#inline-confirmation-listview", ListView)
        listview.focus()
        await pilot.press("enter")

        callback.assert_called_once_with(UserConfirmation.ACCEPT)


@pytest.mark.asyncio
async def test_inline_panel_has_four_options(callback: mock.MagicMock):
    """Test that the inline panel has all four confirmation options."""
    panel = InlineConfirmationPanel(
        num_actions=1,
        confirmation_callback=callback,
    )
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        listview = pilot.app.query_one("#inline-confirmation-listview", ListView)
        # The ListView should have 4 items: accept, reject, always, risky
        assert len(listview.children) == 4
