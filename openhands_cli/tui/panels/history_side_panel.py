"""History side panel widget for switching between conversations."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from textual.app import App
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Static

from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.cloud.lister import CloudConversationLister
from openhands_cli.conversations.lister import ConversationLister
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.panels.history_panel_style import HISTORY_PANEL_STYLE


@dataclass(frozen=True, slots=True)
class HistoryConversationRow:
    """A normalized conversation row for the History panel (local or cloud)."""

    select_id: str
    display_id: str
    created_date: datetime
    first_user_prompt: str | None
    source: str  # "local" | "cloud"


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
        source_prefix = "[dim]cloud[/dim] " if conversation.source == "cloud" else ""

        # Use first_user_prompt as title if available, otherwise use ID
        has_title = bool(conversation.first_user_prompt)
        if conversation.first_user_prompt:
            title = _truncate(conversation.first_user_prompt, 100)
            content = f"{source_prefix}{title}\n[dim]{full_id} • {time_str}[/dim]"
        else:
            content = (
                f"{source_prefix}[dim]New conversation[/dim]\n"
                f"[dim]{full_id} • {time_str}[/dim]"
            )

        super().__init__(content, markup=True, **kwargs)
        self.conversation_id = conversation.select_id
        self._created_date = conversation.created_date
        self._has_title = has_title
        self.is_current = is_current
        self.is_selected = is_selected
        self._on_select = on_select
        self._source = conversation.source

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
        source_prefix = "[dim]cloud[/dim] " if self._source == "cloud" else ""
        display_id = (
            self.conversation_id.removeprefix("cloud:")
            if self._source == "cloud"
            else self.conversation_id
        )
        self.update(
            f"{source_prefix}{title_text}\n[dim]{display_id} • {time_str}[/dim]"
        )
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
    """Side panel widget that displays conversation history."""

    DEFAULT_CSS = HISTORY_PANEL_STYLE
    INITIAL_VISIBLE = 10
    LOAD_MORE_STEP = 10

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
        self._cloud_rows: list[HistoryConversationRow] = []
        self._cloud_loading: bool = False
        self._cloud_error: str | None = None
        self._visible_count: int = self.INITIAL_VISIBLE

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
        self._start_cloud_refresh_if_needed()

    def refresh_content(self) -> None:
        """Reload local conversations and render current visible slice."""
        self._local_rows = self._load_local_rows()
        total_rows = len(self._local_rows) + len(self._cloud_rows)
        if total_rows == 0:
            self._visible_count = self.INITIAL_VISIBLE
        else:
            self._visible_count = min(
                max(self._visible_count, self.INITIAL_VISIBLE),
                total_rows,
            )
        self._render_list()

    def _load_local_rows(self) -> list[HistoryConversationRow]:
        """Load local conversation rows."""
        rows: list[HistoryConversationRow] = []

        # Local conversations
        for conv in ConversationLister().list():
            rows.append(
                HistoryConversationRow(
                    select_id=conv.id,
                    display_id=conv.id,
                    created_date=conv.created_date,
                    first_user_prompt=conv.first_user_prompt,
                    source="local",
                )
            )
        return rows

    def _start_cloud_refresh_if_needed(self) -> None:
        """Fetch cloud conversations in the background (best-effort)."""
        if self._cloud_loading or self._cloud_rows:
            return

        store = TokenStorage()
        if not store.has_api_key():
            return
        api_key = store.get_api_key()
        if not api_key:
            return

        server_url = os.getenv("OPENHANDS_CLOUD_URL", "https://app.all-hands.dev")

        self._cloud_loading = True
        self._cloud_error = None
        self._render_list()

        self.run_worker(
            lambda: self._fetch_cloud_rows_thread(server_url, api_key),
            name="history_cloud_list",
            group="history_cloud_list",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _fetch_cloud_rows_thread(self, server_url: str, api_key: str) -> None:
        """Worker thread: list cloud conversations and update UI."""
        try:
            cloud_convs = CloudConversationLister(server_url, api_key).list()
            cloud_rows: list[HistoryConversationRow] = [
                HistoryConversationRow(
                    select_id=f"cloud:{conv.id}",
                    display_id=conv.id,
                    created_date=conv.created_date,
                    first_user_prompt=conv.title,
                    source="cloud",
                )
                for conv in cloud_convs
            ]

            def _apply() -> None:
                self._cloud_rows = cloud_rows
                self._cloud_loading = False
                self._cloud_error = None
                self._render_list()

            self.app.call_from_thread(_apply)
        except Exception as e:
            error_text = f"{type(e).__name__}: {e}"

            def _apply_error() -> None:
                self._cloud_rows = []
                self._cloud_loading = False
                self._cloud_error = error_text
                self._render_list()

            self.app.call_from_thread(_apply_error)

    def _render_list(self) -> None:
        """Render the current visible slice of conversations."""
        list_container = self.query_one("#history-list", VerticalScroll)
        list_container.remove_children()

        rows: list[HistoryConversationRow] = list(self._local_rows)

        if self._cloud_loading:
            rows.append(
                HistoryConversationRow(
                    select_id="cloud:loading",
                    display_id="cloud",
                    created_date=datetime.now(),
                    first_user_prompt="Loading cloud conversations…",
                    source="cloud",
                )
            )
        elif self._cloud_error:
            rows.append(
                HistoryConversationRow(
                    select_id="cloud:error",
                    display_id="cloud",
                    created_date=datetime.now(),
                    first_user_prompt=f"Cloud unavailable: {self._cloud_error}",
                    source="cloud",
                )
            )
        else:
            rows.extend(self._cloud_rows)

        rows.sort(key=lambda r: r.created_date, reverse=True)

        if not rows:
            list_container.mount(
                Static(
                    f"[{OPENHANDS_THEME.warning}]No conversations yet.\n"
                    f"Start typing to begin![/{OPENHANDS_THEME.warning}]",
                    classes="history-empty",
                )
            )
            return

        visible_items = rows[: self._visible_count]

        current_id_str = (
            self.current_conversation_id.hex if self.current_conversation_id else None
        )
        selected_id_str = (
            self.selected_conversation_id.hex if self.selected_conversation_id else None
        )

        for conv in visible_items:
            is_current = conv.source == "local" and conv.select_id == current_id_str
            is_selected = (
                conv.source == "local"
                and conv.select_id == selected_id_str
                and selected_id_str is not None
            )
            list_container.mount(
                HistoryItem(
                    conversation=conv,
                    is_current=is_current,
                    is_selected=is_selected,
                    on_select=self._handle_select,
                )
            )

        if self._visible_count < len(rows):
            list_container.mount(MoreConversationsItem(self._load_more))

    def _load_more(self) -> None:
        """Load the next chunk of conversations."""
        self._visible_count = self._visible_count + self.LOAD_MORE_STEP
        self._render_list()

    def _handle_select(self, conversation_id: str) -> None:
        """Handle conversation selection."""
        # Cloud conversations are forwarded as "cloud:<id>" and handled by the app.
        if conversation_id.startswith("cloud:") and conversation_id not in (
            "cloud:loading",
            "cloud:error",
        ):
            if self._on_conversation_selected:
                self._on_conversation_selected(conversation_id)
            return

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
            # Only local conversations participate in current/selected highlighting.
            if item.conversation_id.startswith("cloud:"):
                item.set_current(False)
                item.set_selected(False)
                continue
            item.set_current(item.conversation_id == current_hex)
            item.set_selected(item.conversation_id == selected_hex)

    def set_current_conversation(self, conversation_id: uuid.UUID) -> None:
        """Set current conversation and update highlights in-place.

        Also ensures the current conversation is visible in the loaded slice.
        """
        self.current_conversation_id = conversation_id
        self.selected_conversation_id = None

        conv_hex = conversation_id.hex
        for idx, conv in enumerate(self._local_rows):
            if conv.select_id != conv_hex:
                continue
            while self._visible_count <= idx:
                self._visible_count = self._visible_count + self.LOAD_MORE_STEP
            break

        self._render_list()

    def update_conversation_title_if_needed(
        self,
        *,
        conversation_id: uuid.UUID,
        title: str,
    ) -> None:
        """Update 'New conversation' item to first message while panel is open."""
        conv_hex = conversation_id.hex

        # Only local conversations can be updated from in-app first message.
        for i, conv in enumerate(self._local_rows):
            if conv.select_id == conv_hex and not conv.first_user_prompt:
                self._local_rows[i] = HistoryConversationRow(
                    select_id=conv.select_id,
                    display_id=conv.display_id,
                    created_date=conv.created_date,
                    first_user_prompt=title,
                    source=conv.source,
                )
                break

        list_container = self.query_one("#history-list", VerticalScroll)
        for item in list_container.query(HistoryItem):
            if item.conversation_id != conv_hex:
                continue
            if not item._has_title:
                item.set_title(title)
            return


class MoreConversationsItem(Static):
    """A subtle 'More…' row to load more conversations."""

    def __init__(self, on_click: Callable[[], None], **kwargs):
        super().__init__(
            "[dim]… More[/dim]",
            markup=True,
            classes="history-more",
            **kwargs,
        )
        self._on_more = on_click

    def on_click(self, event) -> None:
        del event
        self._on_more()

    # No other behavior here; this is just a clickable row.


def _format_time(dt: datetime) -> str:
    """Format datetime for display."""
    now = datetime.now()
    diff = now - dt

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
