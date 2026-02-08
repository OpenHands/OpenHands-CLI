"""Tests for HistorySidePanel and conversation switching.

The HistorySidePanel uses the ConversationContainer pattern for state updates.
It watches ConversationContainer's reactive properties (conversation_id,
conversation_title, switch_confirmation_target) instead of receiving forwarded messages.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Static

from openhands_cli.conversations.models import ConversationMetadata
from openhands_cli.conversations.store.local import LocalFileStore
from openhands_cli.tui.core import SwitchConversation
from openhands_cli.tui.core.state import ConversationContainer
from openhands_cli.tui.modals.switch_conversation_modal import SwitchConversationModal
from openhands_cli.tui.panels.history_side_panel import (
    HistoryItem,
    HistorySidePanel,
)


class HistoryMessagesTestApp(App):
    """Minimal app for testing HistorySidePanel with ConversationContainer."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Track messages received by the app
        self.received_switch_requests: list[uuid.UUID] = []
        self._store = LocalFileStore()
        # ConversationContainer for reactive state
        self.conversation_state = ConversationContainer()

    def compose(self) -> ComposeResult:
        with Horizontal(id="content_area"):
            yield Static("main", id="main")
            yield self.conversation_state
            yield HistorySidePanel(app=self, current_conversation_id=None)  # type: ignore

    def on_switch_conversation(self, event: SwitchConversation) -> None:
        """Handle switch conversation from history panel."""
        self.received_switch_requests.append(event.conversation_id)


@pytest.mark.asyncio
async def test_history_panel_updates_from_conversation_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the history panel responds to ConversationContainer state changes."""
    # Stub local conversations list.
    base_id = uuid.uuid4().hex
    conversations = [
        ConversationMetadata(
            id=base_id,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            title="hello",
        ),
    ]
    monkeypatch.setattr(
        LocalFileStore, "list_conversations", lambda self, limit=100: conversations
    )

    app = HistoryMessagesTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(HistorySidePanel)

        # Initial render contains the single listed conversation.
        list_container = panel.query_one("#history-list", VerticalScroll)
        assert len(list_container.query(HistoryItem)) == 1

        # Update conversation_id via ConversationContainer (simulating new conversation)
        new_id = uuid.uuid4()
        app.conversation_state.conversation_id = new_id
        await pilot.pause()

        assert panel.current_conversation_id == new_id
        assert panel.selected_conversation_id == new_id

        # Should now have 2 items (existing + placeholder for new).
        assert len(list_container.query(HistoryItem)) == 2
        placeholder_items = [
            item
            for item in list_container.query(HistoryItem)
            if item.conversation_id == new_id.hex
        ]
        assert len(placeholder_items) == 1

        # Update title via ConversationContainer
        app.conversation_state.conversation_title = "first message"
        await pilot.pause()

        placeholder = placeholder_items[0]
        assert "first message" in str(placeholder.content)

        # Test switch confirmation cancellation behavior:
        # Move selection away
        panel._handle_select(base_id)
        assert panel.selected_conversation_id is not None
        assert panel.selected_conversation_id.hex == base_id

        # Simulate a cancelled switch (confirmation target cleared)
        app.conversation_state.switch_confirmation_target = uuid.UUID(base_id)
        await pilot.pause()
        app.conversation_state.switch_confirmation_target = None
        await pilot.pause()

        # Selection should revert to current conversation
        assert panel.selected_conversation_id == panel.current_conversation_id


@pytest.mark.asyncio
async def test_history_panel_posts_switch_request_on_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that selecting a conversation posts SwitchConversation."""
    conv_id = uuid.uuid4().hex
    conversations = [
        ConversationMetadata(
            id=conv_id,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            title="test prompt",
        ),
    ]
    monkeypatch.setattr(
        LocalFileStore, "list_conversations", lambda self, limit=100: conversations
    )

    app = HistoryMessagesTestApp()
    async with app.run_test() as pilot:
        panel = pilot.app.query_one(HistorySidePanel)

        # Simulate selection
        panel._handle_select(conv_id)
        await pilot.pause()

        # Verify that app received the SwitchConversation message
        assert len(app.received_switch_requests) == 1
        assert app.received_switch_requests[0] == uuid.UUID(conv_id)


class SwitchModalTestApp(App):
    """App for testing SwitchConversationModal."""

    def compose(self) -> ComposeResult:
        yield Static("main")


@pytest.mark.asyncio
async def test_switch_modal_result_confirmed() -> None:
    """Test that clicking 'Yes, switch' returns True."""
    app = SwitchModalTestApp()
    async with app.run_test() as pilot:
        modal = SwitchConversationModal(prompt="Switch?")

        result: list[bool | None] = []
        pilot.app.push_screen(modal, result.append)
        await pilot.pause()

        # Click "Yes, switch" button
        yes_button = modal.query_one("#yes", Button)
        yes_button.press()
        await pilot.pause()

        assert result == [True]


@pytest.mark.asyncio
async def test_switch_modal_result_cancelled() -> None:
    """Test that clicking 'No, stay' returns False."""
    app = SwitchModalTestApp()
    async with app.run_test() as pilot:
        modal = SwitchConversationModal(prompt="Switch?")

        result: list[bool | None] = []
        pilot.app.push_screen(modal, result.append)
        await pilot.pause()

        # Click "No, stay" button
        no_button = modal.query_one("#no", Button)
        no_button.press()
        await pilot.pause()

        assert result == [False]
