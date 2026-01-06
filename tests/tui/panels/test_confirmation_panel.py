"""Tests for confirmation panel functionality."""

from __future__ import annotations

from unittest import mock

import pytest
from textual.app import App
from textual.containers import Container, Vertical
from textual.widgets import ListView, Static

from openhands_cli.tui.panels.confirmation_panel import (
    ConfirmationPanel,
    ConfirmationSidePanel,
)
from openhands_cli.user_actions.types import UserConfirmation


class MockActionObject:
    """Mock action object with visualize attribute."""

    def __init__(self, text: str):
        self.visualize = text


class MockActionEvent:
    """Minimal ActionEvent interface used by ConfirmationPanel."""

    def __init__(self, tool_name: str = "unknown", action_text: str = ""):
        self.tool_name = tool_name
        self.action = MockActionObject(action_text) if action_text else None


@pytest.fixture
def callback() -> mock.MagicMock:
    return mock.MagicMock()


def make_actions(
    n: int = 1, tool_name: str = "test_tool", content: str = "test action"
):
    return [MockActionEvent(tool_name, content) for _ in range(n)]


def make_test_app(widget):
    class TestApp(App):
        def compose(self):
            yield widget

    return TestApp()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query, expected_type",
    [
        (".confirmation-header", Static),
        (".actions-container", Container),
        (".confirmation-content", Vertical),
        (".confirmation-instructions", Static),
    ],
)
async def test_confirmation_panel_structure_contains_expected_nodes(
    callback: mock.MagicMock,
    query: str,
    expected_type: type,
):
    panel = ConfirmationPanel(
        pending_actions=make_actions(),  # type: ignore[arg-type]
        confirmation_callback=callback,
    )
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        nodes = pilot.app.query(query)
        assert len(nodes) == 1
        assert isinstance(nodes[0], expected_type)


@pytest.mark.asyncio
async def test_confirmation_panel_has_listview(callback: mock.MagicMock):
    panel = ConfirmationPanel(
        pending_actions=make_actions(),  # type: ignore[arg-type]
        confirmation_callback=callback,
    )
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        assert pilot.app.query_one("#confirmation-listview", ListView) is not None


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
    panel = ConfirmationPanel(
        pending_actions=make_actions(),  # type: ignore[arg-type]
        confirmation_callback=callback,
    )

    mock_item = mock.MagicMock()
    mock_item.id = item_id
    mock_event = mock.MagicMock()
    mock_event.item = mock_item

    panel.on_list_view_selected(mock_event)

    callback.assert_called_once_with(expected_confirmation)


@pytest.mark.asyncio
@pytest.mark.parametrize("num_actions", [1, 3])
async def test_panel_renders_action_items(callback: mock.MagicMock, num_actions: int):
    long_content = "x" * 1000
    actions = [
        MockActionEvent(tool_name, long_content)
        for tool_name in (
            ["file_editor"]
            if num_actions == 1
            else ["file_editor", "execute_bash", "str_replace_editor"]
        )
    ][:num_actions]

    panel = ConfirmationPanel(
        pending_actions=actions,  # type: ignore[arg-type]
        confirmation_callback=callback,
    )
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        action_items = pilot.app.query(".action-item")
        assert len(action_items) == num_actions


@pytest.mark.asyncio
async def test_side_panel_renders_inner_panel_and_listview(callback: mock.MagicMock):
    side_panel = ConfirmationSidePanel(
        pending_actions=make_actions(),  # type: ignore[arg-type]
        confirmation_callback=callback,
    )
    app = make_test_app(side_panel)

    async with app.run_test() as pilot:
        assert pilot.app.query_one(ConfirmationSidePanel) is not None
        assert pilot.app.query_one(ConfirmationPanel) is not None
        assert pilot.app.query_one("#confirmation-listview", ListView) is not None


@pytest.mark.asyncio
async def test_side_panel_is_scrollable_with_long_content(callback: mock.MagicMock):
    long_content = "z" * 5000
    side_panel = ConfirmationSidePanel(
        pending_actions=[MockActionEvent("file_editor", long_content)],  # type: ignore[arg-type]
        confirmation_callback=callback,
    )
    app = make_test_app(side_panel)

    async with app.run_test() as pilot:
        sp = pilot.app.query_one(ConfirmationSidePanel)
        assert sp.is_scrollable

        assert pilot.app.query_one(".actions-container") is not None
        assert pilot.app.query_one("#confirmation-listview", ListView) is not None


@pytest.mark.asyncio
async def test_listview_is_focusable(callback: mock.MagicMock):
    side_panel = ConfirmationSidePanel(
        pending_actions=make_actions(),  # type: ignore[arg-type]
        confirmation_callback=callback,
    )
    app = make_test_app(side_panel)

    async with app.run_test() as pilot:
        listview = pilot.app.query_one("#confirmation-listview", ListView)
        assert listview.can_focus


@pytest.mark.asyncio
async def test_keyboard_enter_selects_first_item_and_calls_callback(
    callback: mock.MagicMock,
):
    side_panel = ConfirmationSidePanel(
        pending_actions=make_actions(),  # type: ignore[arg-type]
        confirmation_callback=callback,
    )
    app = make_test_app(side_panel)

    async with app.run_test() as pilot:
        listview = pilot.app.query_one("#confirmation-listview", ListView)
        listview.focus()
        await pilot.press("enter")

        callback.assert_called_once_with(UserConfirmation.ACCEPT)
