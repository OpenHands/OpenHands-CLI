"""Tests for HistorySidePanel and conversation switching."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.signal import Signal
from textual.widgets import Button, Static

from openhands_cli.conversations.lister import ConversationInfo, ConversationLister
from openhands_cli.tui.modals.switch_conversation_modal import SwitchConversationModal
from openhands_cli.tui.panels.history_side_panel import HistoryItem, HistorySidePanel


class HistorySignalsTestApp(App):
    """Minimal app that exposes history signals for HistorySidePanel to subscribe to."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history_new_conversation_signal = Signal(
            self, "history_new_conversation_signal"
        )
        self.history_current_conversation_signal = Signal(
            self, "history_current_conversation_signal"
        )
        self.history_title_updated_signal = Signal(self, "history_title_updated_signal")
        self.history_select_current_signal = Signal(
            self, "history_select_current_signal"
        )

    def compose(self) -> ComposeResult:
        with Horizontal(id="content_area"):
            yield Static("main", id="main")
            yield HistorySidePanel(current_conversation_id=None)


@pytest.mark.asyncio
async def test_history_panel_updates_from_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Stub local conversations list.
    base_id = uuid.uuid4().hex
    conversations = [
        ConversationInfo(
            id=base_id,
            created_date=datetime(2025, 1, 1, tzinfo=UTC),
            first_user_prompt="hello",
        ),
    ]
    monkeypatch.setattr(ConversationLister, "list", lambda self: conversations)

    app = HistorySignalsTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(HistorySidePanel)

        # Initial render contains the single lister conversation.
        list_container = panel.query_one("#history-list", VerticalScroll)
        assert len(list_container.query(HistoryItem)) == 1

        # Publish "new conversation" → placeholder should be inserted and selected.
        new_id = uuid.uuid4()
        app.history_new_conversation_signal.publish(new_id)
        await pilot.pause()

        assert panel.current_conversation_id == new_id
        assert panel.selected_conversation_id == new_id

        # Should now have 2 items (existing + placeholder).
        assert len(list_container.query(HistoryItem)) == 2
        placeholder_items = [
            item
            for item in list_container.query(HistoryItem)
            if item.conversation_id == new_id.hex
        ]
        assert len(placeholder_items) == 1

        # Publish title update → placeholder item should display title.
        app.history_title_updated_signal.publish((new_id, "first message"))
        await pilot.pause()

        placeholder = placeholder_items[0]
        assert "first message" in str(placeholder.content)

        # Move selection away and then revert via select-current signal.
        panel._handle_select(base_id)
        assert panel.selected_conversation_id is not None
        assert panel.selected_conversation_id.hex == base_id

        app.history_select_current_signal.publish(True)
        await pilot.pause()
        assert panel.selected_conversation_id == panel.current_conversation_id


@pytest.mark.asyncio
async def test_history_panel_conversation_selection_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that selecting a conversation triggers the on_select callback."""
    conv_id = uuid.uuid4().hex
    conversations = [
        ConversationInfo(
            id=conv_id,
            created_date=datetime(2025, 1, 1, tzinfo=UTC),
            first_user_prompt="test prompt",
        ),
    ]
    monkeypatch.setattr(ConversationLister, "list", lambda self: conversations)

    selected_ids: list[str] = []

    def on_select(cid: str) -> None:
        selected_ids.append(cid)

    app = HistorySignalsTestApp()
    async with app.run_test() as pilot:
        panel = pilot.app.query_one(HistorySidePanel)
        panel._on_conversation_selected = on_select

        # Simulate selection
        panel._handle_select(conv_id)
        await pilot.pause()

        assert len(selected_ids) == 1
        assert selected_ids[0] == conv_id


class SwitchModalTestApp(App):
    """App for testing SwitchConversationModal."""

    def compose(self) -> ComposeResult:
        yield Static("main")


@pytest.mark.asyncio
async def test_switch_modal_confirm_calls_on_confirmed() -> None:
    """Test that clicking 'Yes, switch' calls on_confirmed callback."""
    confirmed_called = []
    cancelled_called = []

    app = SwitchModalTestApp()
    async with app.run_test() as pilot:
        modal = SwitchConversationModal(
            prompt="Switch?",
            on_confirmed=lambda: confirmed_called.append(True),
            on_cancelled=lambda: cancelled_called.append(True),
        )
        pilot.app.push_screen(modal)
        await pilot.pause()

        # Click "Yes, switch" button
        yes_button = modal.query_one("#yes", Button)
        yes_button.press()
        await pilot.pause()

        assert len(confirmed_called) == 1
        assert len(cancelled_called) == 0


@pytest.mark.asyncio
async def test_switch_modal_cancel_calls_on_cancelled() -> None:
    """Test that clicking 'No, stay' calls on_cancelled callback."""
    confirmed_called = []
    cancelled_called = []

    app = SwitchModalTestApp()
    async with app.run_test() as pilot:
        modal = SwitchConversationModal(
            prompt="Switch?",
            on_confirmed=lambda: confirmed_called.append(True),
            on_cancelled=lambda: cancelled_called.append(True),
        )
        pilot.app.push_screen(modal)
        await pilot.pause()

        # Click "No, stay" button
        no_button = modal.query_one("#no", Button)
        no_button.press()
        await pilot.pause()

        assert len(confirmed_called) == 0
        assert len(cancelled_called) == 1
