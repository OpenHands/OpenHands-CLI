"""Tests for inline confirmation panel functionality."""

from __future__ import annotations

from unittest import mock

import pytest
from textual.app import App
from textual.containers import Vertical
from textual.widgets import ListView, Static

from openhands_cli.tui.core.events import ConfirmationDecision
from openhands_cli.tui.panels.confirmation_panel import (
    InlineConfirmationPanel,
    _KeyboardOnlyListView,
)
from openhands_cli.user_actions.types import UserConfirmation


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
    query: str,
    expected_type: type,
):
    panel = InlineConfirmationPanel(num_actions=1)
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        nodes = pilot.app.query(query)
        assert len(nodes) == 1
        assert isinstance(nodes[0], expected_type)


@pytest.mark.asyncio
async def test_inline_confirmation_panel_has_listview():
    panel = InlineConfirmationPanel(num_actions=1)
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
    item_id: str,
    expected_confirmation: UserConfirmation,
):
    """Test that selecting an item posts the correct ConfirmationDecision message."""
    panel = InlineConfirmationPanel(num_actions=1)

    mock_item = mock.MagicMock()
    mock_item.id = item_id
    mock_event = mock.MagicMock()
    mock_event.item = mock_item

    # Mock post_message to capture the message, and _remove_self since there's no app
    with (
        mock.patch.object(panel, "post_message") as mock_post,
        mock.patch.object(panel, "_remove_self"),
    ):
        panel.on_list_view_selected(mock_event)

        mock_post.assert_called_once()
        posted_message = mock_post.call_args[0][0]
        assert isinstance(posted_message, ConfirmationDecision)
        assert posted_message.decision == expected_confirmation


@pytest.mark.asyncio
@pytest.mark.parametrize("num_actions", [1, 3, 5])
async def test_inline_panel_displays_correct_action_count(num_actions: int):
    panel = InlineConfirmationPanel(num_actions=num_actions)
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        # Verify the panel was created with the correct num_actions
        inline_panel = pilot.app.query_one(InlineConfirmationPanel)
        assert inline_panel.num_actions == num_actions


@pytest.mark.asyncio
async def test_inline_panel_renders_and_listview_exists():
    panel = InlineConfirmationPanel(num_actions=2)
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        assert pilot.app.query_one(InlineConfirmationPanel) is not None
        assert (
            pilot.app.query_one("#inline-confirmation-listview", ListView) is not None
        )


@pytest.mark.asyncio
async def test_listview_is_focusable():
    panel = InlineConfirmationPanel(num_actions=1)
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        listview = pilot.app.query_one("#inline-confirmation-listview", ListView)
        assert listview.can_focus


@pytest.mark.asyncio
async def test_keyboard_enter_selects_first_item_and_posts_message():
    """Test that pressing enter on first item posts ConfirmationDecision message."""
    messages_received = []

    class TestApp(App):
        def compose(self):
            yield InlineConfirmationPanel(num_actions=1)

        def on_confirmation_decision(self, event: ConfirmationDecision) -> None:
            messages_received.append(event)

    app = TestApp()

    async with app.run_test() as pilot:
        listview = pilot.app.query_one("#inline-confirmation-listview", ListView)
        listview.focus()
        await pilot.press("enter")

        assert len(messages_received) == 1
        assert messages_received[0].decision == UserConfirmation.ACCEPT


@pytest.mark.asyncio
async def test_inline_panel_has_four_options():
    """Test that the inline panel has all four confirmation options."""
    panel = InlineConfirmationPanel(num_actions=1)
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        listview = pilot.app.query_one("#inline-confirmation-listview", ListView)
        # The ListView should have 4 items: accept, reject, always, risky
        assert len(listview.children) == 4


# ============================================================================
# Keyboard-only list view — mouse click must NOT post ListView.Selected
# ============================================================================


@pytest.mark.asyncio
async def test_inline_panel_uses_keyboard_only_list_view():
    """The confirmation list must be a _KeyboardOnlyListView instance."""
    panel = InlineConfirmationPanel(num_actions=1)
    app = make_test_app(panel)

    async with app.run_test() as pilot:
        listview = pilot.app.query_one("#inline-confirmation-listview", ListView)
        assert isinstance(listview, _KeyboardOnlyListView), (
            "InlineConfirmationPanel must use _KeyboardOnlyListView to prevent "
            "accidental mouse-click confirmations."
        )


def test_keyboard_only_list_view_click_does_not_post_selected():
    """A child-click on _KeyboardOnlyListView must NOT post ListView.Selected.

    This guards against the misfire: a mouse click near the confirmation panel
    would previously immediately accept/reject the pending action.
    """
    from textual.widgets import ListItem

    lv = _KeyboardOnlyListView(ListItem(Static("Yes")))
    selected_messages: list[object] = []

    mock_item = mock.MagicMock()
    mock_item.id = "accept"
    mock_nodes = mock.MagicMock()
    mock_nodes.index.return_value = 0

    # Wire up post_message to capture any Selected messages; also patch
    # focus() and _nodes (which require an active Textual app context).
    with (
        mock.patch.object(lv, "post_message", side_effect=selected_messages.append),
        mock.patch.object(lv, "focus"),
        mock.patch.object(lv, "_nodes", mock_nodes),
    ):
        child_click_event = mock.MagicMock(spec=ListItem._ChildClicked)
        child_click_event.item = mock_item
        lv._on_list_item__child_clicked(child_click_event)

    selected = [m for m in selected_messages if isinstance(m, ListView.Selected)]
    assert selected == [], (
        "_KeyboardOnlyListView._on_list_item__child_clicked must NOT post "
        "ListView.Selected so that mouse clicks cannot trigger confirmations."
    )
