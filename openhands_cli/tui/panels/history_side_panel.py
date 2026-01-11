"""History side panel widget for switching between conversations."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from textual.app import App
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Static

from openhands_cli.conversations.lister import ConversationLister
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.panels.history_panel_style import HISTORY_PANEL_STYLE


@dataclass(frozen=True, slots=True)
class HistoryConversationRow:
    """A normalized conversation row for the History panel (local only)."""

    select_id: str
    display_id: str
    created_date: datetime
    first_user_prompt: str | None


class HistoryItem(Static):
    """A clickable conversation item in the history panel."""

    def __init__(
        self,
        conversation: HistoryConversationRow,
        is_current: bool,
        is_selected: bool,
        on_select: Callable[[str], None],
        **kwargs,
    ):
        """Initialize history item.

        Args:
            conversation: The conversation info to display
            is_current: Whether this is the currently active conversation
            on_select: Callback when this item is selected
        """
        # Build the content string - show first_user_prompt as title, id as secondary
        time_str = _format_time(conversation.created_date)
        full_id = conversation.display_id
        short_id = full_id[:8]

        # Use first_user_prompt as title if available, otherwise use ID
        has_title = bool(conversation.first_user_prompt)
        if conversation.first_user_prompt:
            title = _truncate(conversation.first_user_prompt, 100)
            content = f"{title}\n[dim]{short_id} • {time_str}[/dim]"
        else:
            content = f"[dim]New conversation[/dim]\n[dim]{short_id} • {time_str}[/dim]"

        super().__init__(content, markup=True, **kwargs)
        self.conversation_id = conversation.select_id
        self._created_date = conversation.created_date
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

    def on_click(self) -> None:
        """Handle click on history item."""
        self._on_select(self.conversation_id)

    def set_title(self, title: str) -> None:
        """Update the displayed title for this history item."""
        time_str = _format_time(self._created_date)
        title_text = _truncate(title, 100)
        short_id = self.conversation_id[:8]
        self.update(f"{title_text}\n[dim]{short_id} • {time_str}[/dim]")
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
        current_conversation_id: uuid.UUID | None = None,
        on_conversation_selected: Callable[[str], None] | None = None,
        **kwargs,
    ):
        """Initialize the history side panel.

        Args:
            current_conversation_id: The currently active conversation ID
            on_conversation_selected: Callback when a conversation is selected
        """
        super().__init__(**kwargs)
        self.current_conversation_id = current_conversation_id
        self.selected_conversation_id: uuid.UUID | None = None
        self._on_conversation_selected = on_conversation_selected
        self._local_rows: list[HistoryConversationRow] = []

    @classmethod
    def toggle(
        cls,
        app: App,
        current_conversation_id: uuid.UUID | None = None,
        on_conversation_selected: Callable[[str], None] | None = None,
    ) -> None:
        """Toggle the history side panel on/off.

        Args:
            app: The Textual app instance
            current_conversation_id: The currently active conversation ID
            on_conversation_selected: Callback when a conversation is selected
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
            current_conversation_id=current_conversation_id,
            on_conversation_selected=on_conversation_selected,
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

    def refresh_content(self) -> None:
        """Reload conversations and render the list."""
        self._local_rows = self._load_local_rows()
        self._render_list()

    def _load_local_rows(self) -> list[HistoryConversationRow]:
        """Load local conversation rows."""
        rows: list[HistoryConversationRow] = []
        for conv in ConversationLister().list():
            rows.append(
                HistoryConversationRow(
                    select_id=conv.id,
                    display_id=conv.id,
                    created_date=conv.created_date,
                    first_user_prompt=conv.first_user_prompt,
                )
            )
        return rows

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
            is_current = conv.select_id == current_id_str
            is_selected = (
                conv.select_id == selected_id_str and selected_id_str is not None
            )
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

        if self._on_conversation_selected:
            self._on_conversation_selected(conversation_id)

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
        self._render_list()

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
        if any(row.select_id == conv_hex for row in self._local_rows):
            return

        self._local_rows.insert(
            0,
            HistoryConversationRow(
                select_id=conv_hex,
                display_id=conv_hex,
                created_date=datetime.now(),
                first_user_prompt=None,
            ),
        )

    def update_conversation_title_if_needed(
        self,
        *,
        conversation_id: uuid.UUID,
        title: str,
    ) -> None:
        """Update 'New conversation' item to first message while panel is open."""
        conv_hex = conversation_id.hex

        for i, conv in enumerate(self._local_rows):
            if conv.select_id == conv_hex and not conv.first_user_prompt:
                self._local_rows[i] = HistoryConversationRow(
                    select_id=conv.select_id,
                    display_id=conv.display_id,
                    created_date=conv.created_date,
                    first_user_prompt=title,
                )
                break

        list_container = self.query_one("#history-list", VerticalScroll)
        for item in list_container.query(HistoryItem):
            if item.conversation_id != conv_hex:
                continue
            if not item._has_title:
                item.set_title(title)
            return


def _format_time(dt: datetime) -> str:
    """Format datetime for display."""
    # Be defensive: normalize now to dt's timezone if needed.
    now = datetime.now(dt.tzinfo) if dt.tzinfo is not None else datetime.now()
    diff = now - dt
    # If timestamp is slightly in the future (clock skew), clamp to 0.
    if diff.total_seconds() < 0:
        diff = timedelta(seconds=0)

    if diff.days == 0:
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
