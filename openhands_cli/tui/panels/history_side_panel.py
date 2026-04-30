"""History side panel widget for switching between conversations.

This panel watches ConversationContainer for conversation state changes instead of
receiving forwarded messages. When mounted, it subscribes to:
- conversation_id: to update current/selected highlighting
- conversation_title: to update the title display for new conversations
- switch_confirmation_target: to revert selection when switch is cancelled

Conversation switching is done by posting SwitchConversation messages to
ConversationManager.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.widgets import Button, ListItem, ListView, Static

from openhands_cli.conversations.models import ConversationMetadata
from openhands_cli.conversations.store.local import LocalFileStore
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.panels.history_panel_style import HISTORY_PANEL_STYLE


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


def _escape_rich_markup(text: str) -> str:
    """Escape Rich markup characters in text to prevent markup errors."""
    return text.replace("[", r"\[").replace("]", r"\]")


class HistoryItemContent(Static):
    """Content widget for a conversation item in the history panel."""

    def __init__(
        self,
        conversation: ConversationMetadata,
        is_current: bool,
        **kwargs,
    ):
        """Initialize history item content.

        Args:
            conversation: The conversation metadata to display
            is_current: Whether this is the currently active conversation
        """
        # Build the content string - show title, id as secondary
        time_str = _format_time(conversation.created_at)
        conv_id = _escape_rich_markup(conversation.id)

        # Use title if available, otherwise use ID
        has_title = bool(conversation.title)
        if conversation.title:
            title = _escape_rich_markup(_truncate(conversation.title, 100))
            content = f"{title}\n[dim]{conv_id} • {time_str}[/dim]"
        else:
            content = f"[dim]New conversation[/dim]\n[dim]{conv_id} • {time_str}[/dim]"

        super().__init__(content, markup=True, **kwargs)
        self.conversation_id = conversation.id
        self._created_at = conversation.created_at
        self._has_title = has_title
        self.is_current = is_current

        # Add appropriate class for styling
        self.add_class("history-item-content")
        if is_current:
            self.add_class("history-item-current")

    @property
    def has_title(self) -> bool:
        """Check if this item already has a user-provided title."""
        return self._has_title

    def set_title(self, title: str) -> None:
        """Update the displayed title for this history item."""
        time_str = _format_time(self._created_at)
        title_text = _escape_rich_markup(_truncate(title, 100))
        conv_id = _escape_rich_markup(self.conversation_id)
        self.update(f"{title_text}\n[dim]{conv_id} • {time_str}[/dim]")
        self._has_title = True

    def set_current(self, is_current: bool) -> None:
        """Set current flag and update styles."""
        self.is_current = is_current
        if is_current:
            self.add_class("history-item-current")
        else:
            self.remove_class("history-item-current")


# Keep the close button out of the focus order so reverse traversal matches
# the app-level Tab override which makes button unreachable using tab only.
# That makes /history or pallete menu the only way to close the panel from
# the keyboard.
class HistoryCloseButton(Button, can_focus=False):
    pass


class HistorySidePanel(Container):
    """Side panel widget that displays conversation history (local only).

    This panel watches ConversationContainer for state changes instead of receiving
    forwarded messages. This eliminates the need for manual message routing
    through OpenHandsApp.
    """

    DEFAULT_CSS = HISTORY_PANEL_STYLE

    def __init__(
        self,
        app: OpenHandsApp,
        current_conversation_id: uuid.UUID | None = None,
        **kwargs,
    ):
        """Initialize the history side panel.

        Args:
            app: The OpenHands app instance
            current_conversation_id: The currently active conversation ID
        """
        super().__init__(**kwargs)
        self._oh_app = app
        self.current_conversation_id = current_conversation_id
        self.selected_conversation_id: uuid.UUID | None = None
        self._local_rows: list[ConversationMetadata] = []
        self._previous_switch_confirmation_target: uuid.UUID | None = None
        self._store = LocalFileStore()

    @classmethod
    def toggle(
        cls,
        app: OpenHandsApp,
        current_conversation_id: uuid.UUID | None = None,
    ) -> None:
        """Toggle the history side panel on/off.

        Args:
            app: The OpenHands app instance
            current_conversation_id: The currently active conversation ID
        """
        try:
            existing = app.query_one(cls)
        except NoMatches:
            existing = None

        if existing is not None:
            existing.remove()
            return

        content_area = app.query_one("#content_area", Horizontal)
        panel = cls(
            app=app,
            current_conversation_id=current_conversation_id,
        )
        content_area.mount(panel)

    def compose(self) -> ComposeResult:
        """Compose the history side panel content."""
        with Horizontal(classes="history-header-row"):
            yield Static("Conversations", classes="history-header", id="history-header")
            yield HistoryCloseButton(
                "✕", id="history-close-btn", classes="history-close-btn"
            )
        yield ListView(id="history-list")

    def on_mount(self) -> None:
        """Called when the panel is mounted.

        Sets up watchers on ConversationContainer to react to state changes.
        """
        state = self._oh_app.conversation_state

        # Initialize from current state
        self.current_conversation_id = state.conversation_id
        self.selected_conversation_id = self.current_conversation_id
        self._previous_switch_confirmation_target = state.switch_confirmation_target

        # Load and render conversations first
        self.refresh_content()

        # Watch ConversationContainer for changes
        # (init=False prevents immediate callback during setup)
        self.watch(
            state, "conversation_id", self._on_conversation_id_changed, init=False
        )
        self.watch(
            state, "conversation_title", self._on_conversation_title_changed, init=False
        )
        self.watch(
            state,
            "switch_confirmation_target",
            self._on_switch_confirmation_target_changed,
            init=False,
        )

        # Focus the ListView to enable keyboard navigation
        list_view = self.query_one("#history-list", ListView)
        list_view.focus()

    # --- ConversationContainer Watchers ---

    def _on_conversation_id_changed(self, new_id: uuid.UUID | None) -> None:
        """React to conversation_id changes in ConversationContainer.

        This handles both new conversation creation and conversation switching.
        """
        if new_id is None:
            return

        # Ensure the conversation is visible in the list (for new conversations)
        self.ensure_conversation_visible(new_id)

        # Update current and selection
        self.set_current_conversation(new_id)
        self.select_current_conversation()

    def _on_conversation_title_changed(self, new_title: str | None) -> None:
        """React to conversation_title changes in ConversationContainer."""
        if new_title and self.current_conversation_id:
            self.update_conversation_title_if_needed(
                conversation_id=self.current_conversation_id,
                title=new_title,
            )

    def _on_switch_confirmation_target_changed(
        self, target_id: uuid.UUID | None
    ) -> None:
        """React to switch confirmation cancellation.

        When a switch confirmation is dismissed (target_id goes from UUID to None)
        and the conversation_id hasn't changed, revert the selection highlight.
        """
        previous_target = self._previous_switch_confirmation_target
        self._previous_switch_confirmation_target = target_id

        if previous_target is not None and target_id is None:
            current_state_id = self._oh_app.conversation_state.conversation_id
            if current_state_id == self.current_conversation_id:
                self.select_current_conversation()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle close button: remove panel (same as /history again)."""
        if event.button.id == "history-close-btn":
            self.remove()

    def key_escape(self) -> None:
        """Handle Escape key: close the history panel."""
        self.remove()

    def refresh_content(self) -> None:
        """Reload conversations and render the list."""
        self._local_rows = self._store.list_conversations()

        if self.current_conversation_id is not None and not any(
            row.id == self.current_conversation_id.hex for row in self._local_rows
        ):
            # Synthesize a placeholder row for the active conversation so the
            # history panel can show and focus it before persistence catches up.
            self._local_rows.insert(
                0,
                ConversationMetadata(
                    id=self.current_conversation_id.hex,
                    created_at=datetime.now(),
                    title=None,
                ),
            )

        self._render_list()

    def _render_list(self) -> None:
        """Render the conversation list."""
        list_view = self.query_one("#history-list", ListView)
        list_view.clear()

        if not self._local_rows:
            # Render the "No conversations yet" empty state.
            list_view.mount(
                ListItem(
                    Static(
                        f"[{OPENHANDS_THEME.warning}]No conversations yet.\n"
                        f"Start typing to begin![/{OPENHANDS_THEME.warning}]",
                        classes="history-empty",
                    )
                )
            )
            return

        current_id_str = (
            self.current_conversation_id.hex if self.current_conversation_id else None
        )

        # Track which index should be initially highlighted
        initial_index = 0
        for i, conv in enumerate(self._local_rows):
            is_current = conv.id == current_id_str
            if is_current:
                initial_index = i

            content = HistoryItemContent(
                conversation=conv,
                is_current=is_current,
            )
            list_view.mount(ListItem(content, id=f"history-item-{conv.id}"))

        # Set initial highlight to current conversation
        if self._local_rows:
            list_view.index = initial_index

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle ListView selection (Enter key or click).
        Posts SwitchConversation."""
        from openhands_cli.tui.core import SwitchConversation

        if event.item is None or event.item.id is None:
            return

        # Extract conversation ID from the ListItem id.
        # Format: "history-item-{conv_id}"
        item_id = event.item.id
        if not item_id.startswith("history-item-"):
            return

        conversation_id_str = item_id.replace("history-item-", "")
        conversation_id = uuid.UUID(conversation_id_str)

        self.selected_conversation_id = conversation_id
        self._update_highlights()

        # Message bubbles up to ConversationManager (ancestor via content_area)
        self.post_message(SwitchConversation(conversation_id))

    def _update_highlights(self) -> None:
        """Update current/selected highlights without reloading the list."""
        current_hex = (
            self.current_conversation_id.hex if self.current_conversation_id else None
        )
        list_view = self.query_one("#history-list", ListView)
        for list_item in list_view.query(ListItem):
            # Get the HistoryItemContent from the ListItem
            content_widgets = list_item.query(HistoryItemContent)
            if content_widgets:
                content = content_widgets.first()
                content.set_current(content.conversation_id == current_hex)

    def set_current_conversation(self, conversation_id: uuid.UUID) -> None:
        """Set current conversation and update highlights in-place."""
        self.current_conversation_id = conversation_id
        self.selected_conversation_id = None
        self._update_highlights()

    def select_current_conversation(self) -> None:
        """Select the current conversation in the list (without switching)."""
        if self.current_conversation_id is None:
            return
        self.selected_conversation_id = self.current_conversation_id
        self._update_highlights()

    def ensure_conversation_visible(self, conversation_id: uuid.UUID) -> None:
        """Ensure a conversation row exists in the list (even before persistence).

        This is used for newly created conversations so the history panel can
        immediately show and select them.
        """
        conv_hex = conversation_id.hex
        # Check if already in the local rows
        if any(row.id == conv_hex for row in self._local_rows):
            return

        # Add to local rows
        new_conv = ConversationMetadata(
            id=conv_hex, created_at=datetime.now(), title=None
        )
        self._local_rows.insert(0, new_conv)

        # Replace the empty-state row before prepending a real history item.
        list_view = self.query_one("#history-list", ListView)
        if (
            len(list_view.query(HistoryItemContent)) == 0
            and len(list_view.children) > 0
        ):
            self.call_after_refresh(self._render_list)
            return

        content = HistoryItemContent(
            conversation=new_conv,
            is_current=(
                conv_hex
                == (
                    self.current_conversation_id.hex
                    if self.current_conversation_id
                    else None
                )
            ),
        )
        list_view.mount(ListItem(content, id=f"history-item-{conv_hex}"), before=0)

    def update_conversation_title_if_needed(
        self,
        *,
        conversation_id: uuid.UUID,
        title: str,
    ) -> None:
        """Update 'New conversation' item to first message while panel is open."""
        conv_hex = conversation_id.hex

        for i, conv in enumerate(self._local_rows):
            if conv.id == conv_hex and not conv.title:
                # Update the object in the list
                # (dataclass replace would be cleaner but this works for now)
                # Since it's a dataclass, we can construct a new one.
                self._local_rows[i] = ConversationMetadata(
                    id=conv.id,
                    created_at=conv.created_at,
                    title=title,
                    last_modified=conv.last_modified,
                )
                break

        # 2. Update UI widget in-place if it exists (Source of Truth vs UI)
        list_view = self.query_one("#history-list", ListView)
        for list_item in list_view.query(ListItem):
            content_widgets = list_item.query(HistoryItemContent)
            if content_widgets:
                content = content_widgets.first()
                if content.conversation_id == conv_hex:
                    if not content.has_title:
                        content.set_title(title)
                    break


def _format_time(dt: datetime) -> str:
    """Format datetime for display."""
    # Be defensive: normalize now to dt's timezone if needed.
    now = datetime.now(dt.tzinfo) if dt.tzinfo is not None else datetime.now()
    diff = now - dt
    # If timestamp is slightly in the future (clock skew), clamp to 0.
    if diff.total_seconds() < 0:
        diff = timedelta(seconds=0)

    if diff.days == 0:
        if diff.seconds < 60:
            return "just now"
        if diff.seconds < 3600:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
    elif diff.days == 1:
        return "yesterday"
    elif diff.days < 7:
        return f"{diff.days}d ago"
    else:
        return dt.strftime("%Y-%m-%d")


def _truncate(text: str, max_length: int) -> str:
    """Truncate text for display."""
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
