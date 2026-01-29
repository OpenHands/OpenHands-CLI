"""History side panel widget for switching between conversations."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from textual import on
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Static

from openhands_cli.conversations.models import ConversationMetadata
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.core.messages import (
    ConversationCreated,
    ConversationSwitched,
    ConversationTitleUpdated,
    RevertSelectionRequest,
    SwitchConversationRequest,
)
from openhands_cli.tui.panels.history_panel_style import HISTORY_PANEL_STYLE


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


def _escape_rich_markup(text: str) -> str:
    """Escape Rich markup characters in text to prevent markup errors."""
    return text.replace("[", r"\[").replace("]", r"\]")


class HistoryItem(Static):
    """A clickable conversation item in the history panel."""

    def __init__(
        self,
        conversation: ConversationMetadata,
        is_current: bool,
        is_selected: bool,
        on_select: Callable[[str], None],
        **kwargs,
    ):
        """Initialize history item.

        Args:
            conversation: The conversation metadata to display
            is_current: Whether this is the currently active conversation
            on_select: Callback when this item is selected
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
        self.is_selected = is_selected
        self._on_select = on_select

        # Add appropriate class for styling
        self.add_class("history-item")
        self._apply_state_classes()

    def _apply_state_classes(self) -> None:
        """Apply CSS classes based on current/selected state."""
        if self.is_current:
            self.add_class("history-item-current")
        else:
            self.remove_class("history-item-current")

        if self.is_selected and not self.is_current:
            self.add_class("history-item-selected")
        else:
            self.remove_class("history-item-selected")

    @property
    def has_title(self) -> bool:
        """Check if this item already has a user-provided title."""
        return self._has_title

    def on_click(self) -> None:
        """Handle click on history item."""
        self._on_select(self.conversation_id)

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
            self.is_selected = False
        self._apply_state_classes()

    def set_selected(self, is_selected: bool) -> None:
        """Set selected flag and update styles."""
        self.is_selected = is_selected
        self._apply_state_classes()


class HistorySidePanel(Container):
    """Side panel widget that displays conversation history (local only)."""

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

    def compose(self):
        """Compose the history side panel content."""
        yield Static("Conversations", classes="history-header", id="history-header")
        yield VerticalScroll(id="history-list")

    def on_mount(self):
        """Called when the panel is mounted."""
        self.selected_conversation_id = self.current_conversation_id
        self.refresh_content()
        # Ensure current conversation is visible even if not yet persisted
        if self.current_conversation_id is not None:
            self.ensure_conversation_visible(self.current_conversation_id)

    # --- Message Handlers (using Textual's native message system) ---

    @on(ConversationCreated)
    def _on_conversation_created(self, event: ConversationCreated) -> None:
        """Handle message: a new conversation was created."""
        self.ensure_conversation_visible(event.conversation_id)
        self.set_current_conversation(event.conversation_id)
        self.select_current_conversation()

    @on(ConversationSwitched)
    def _on_conversation_switched(self, event: ConversationSwitched) -> None:
        """Handle message: current conversation changed."""
        self.set_current_conversation(event.conversation_id)

    @on(ConversationTitleUpdated)
    def _on_conversation_title_updated(self, event: ConversationTitleUpdated) -> None:
        """Handle message: conversation title should be updated."""
        self.update_conversation_title_if_needed(
            conversation_id=event.conversation_id, title=event.title
        )

    @on(RevertSelectionRequest)
    def _on_revert_selection(self, _event: RevertSelectionRequest) -> None:
        """Handle message: revert selection highlight to the current conversation."""
        self.select_current_conversation()

    def refresh_content(self) -> None:
        """Reload conversations and render the list."""
        self._local_rows = self._load_local_rows()
        self._render_list()

    def _load_local_rows(self) -> list[ConversationMetadata]:
        """Load local conversation rows."""
        return self._oh_app._conversation_manager.list_conversations()

    def _render_list(self) -> None:
        """Render the conversation list."""
        list_container = self.query_one("#history-list", VerticalScroll)
        list_container.remove_children()

        if not self._local_rows:
            list_container.mount(
                Static(
                    f"[{OPENHANDS_THEME.warning}]No conversations yet.\n"
                    f"Start typing to begin![/{OPENHANDS_THEME.warning}]",
                    classes="history-empty",
                )
            )
            return

        current_id_str = (
            self.current_conversation_id.hex if self.current_conversation_id else None
        )
        selected_id_str = (
            self.selected_conversation_id.hex if self.selected_conversation_id else None
        )

        for conv in self._local_rows:
            is_current = conv.id == current_id_str
            is_selected = conv.id == selected_id_str and selected_id_str is not None
            list_container.mount(
                HistoryItem(
                    conversation=conv,
                    is_current=is_current,
                    is_selected=is_selected,
                    on_select=self._handle_select,
                )
            )

    def _handle_select(self, conversation_id: str) -> None:
        """Handle conversation selection."""
        self.selected_conversation_id = uuid.UUID(conversation_id)
        self._update_highlights()

        # Post a message to request conversation switch (App will handle it)
        self.post_message(SwitchConversationRequest(conversation_id))

    def _update_highlights(self) -> None:
        """Update current/selected highlights without reloading the list."""
        current_hex = (
            self.current_conversation_id.hex if self.current_conversation_id else None
        )
        selected_hex = (
            self.selected_conversation_id.hex if self.selected_conversation_id else None
        )
        list_container = self.query_one("#history-list", VerticalScroll)
        for item in list_container.query(HistoryItem):
            item.set_current(item.conversation_id == current_hex)
            item.set_selected(item.conversation_id == selected_hex)

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
        if any(row.id == conv_hex for row in self._local_rows):
            return

        self._local_rows.insert(
            0,
            ConversationMetadata(id=conv_hex, created_at=datetime.now(), title=None),
        )
        self._render_list()

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
        for item in self.query(HistoryItem):
            if item.conversation_id == conv_hex:
                if not item.has_title:
                    item.set_title(title)
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
