"""Smart container for conversation history rendering.

This pane handles:
- Rendering conversation history events (user messages, actions, observations)
- Scrolling to latest content
- Caching rendered content (for fast switching between conversations)
- Pagination with "Load More" button for older history

Note: This is for events within ONE conversation, not the list of all
conversations (which is handled by HistorySidePanel). The conversation ID
is shown in SystemSplashPane, not here.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Static

from openhands.sdk.event import MessageEvent
from openhands.sdk.event.base import Event
from openhands_cli.tui.core.conversation_history_manager import (
    ConversationHistoryManager,
)
from openhands_cli.tui.core.messages import RenderConversationHistory


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp
    from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


class LoadMoreButton(Button):
    """Button to load more conversation history.

    Shows at the top of a conversation pane when there are older events
    to load. Displays remaining count and handles click to trigger loading.
    """

    DEFAULT_CSS = """
    LoadMoreButton {
        width: 100%;
        height: auto;
        min-height: 1;
        background: $surface;
        color: $text-muted;
        border: none;
        text-style: italic;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    LoadMoreButton:hover {
        background: $surface-lighten-1;
        color: $text;
    }
    LoadMoreButton:focus {
        background: $surface-lighten-1;
    }
    LoadMoreButton.-hidden {
        display: none;
    }
    """

    class Clicked(Message):
        """Message emitted when Load More button is clicked."""

        def __init__(self, pane: ConversationPane) -> None:
            super().__init__()
            self.pane = pane

    def __init__(self, remaining: int = 0, **kwargs) -> None:
        label = self._format_label(remaining)
        super().__init__(label, **kwargs)
        self._remaining = remaining

    def _format_label(self, remaining: int) -> str:
        """Format button label with remaining count."""
        if remaining <= 0:
            return "⬆ Load more history"
        return f"⬆ Load more history ({remaining} remaining)"

    def update_remaining(self, remaining: int) -> None:
        """Update the remaining count and refresh label."""
        self._remaining = remaining
        self.label = self._format_label(remaining)
        # Hide if no more to load
        if remaining <= 0:
            self.add_class("-hidden")
        else:
            self.remove_class("-hidden")


class ConversationPane(Container):
    """Smart container for conversation-specific content and history rendering.

    Each pane is bound to a specific conversation_id and contains:
    - Its own content container (VerticalScroll) for chat messages
    - Its own ConversationHistoryManager for pagination state

    For multi-chat caching: multiple panes can exist simultaneously.
    When switching conversations, we hide/show panes instead of re-rendering.
    This provides instant switching without reloading from disk.

    This follows the same pattern as HistorySidePanel: the pane owns its state
    and listens for messages to update itself.
    """

    # CSS class constants
    CLASS_PANE_HEADER = "pane-header"
    CLASS_VISIBLE = "visible"
    ID_HEADER = "pane_conversation_header"
    ID_LOAD_MORE = "load_more_button"

    DEFAULT_CSS = """
    ConversationPane {
        height: auto;
        width: 100%;
    }
    ConversationPane .pane-header {
        height: auto;
        padding: 0 1;
        display: none;
    }
    ConversationPane .pane-header.visible {
        display: block;
    }
    """

    def __init__(self, conversation_id: uuid.UUID, show_header: bool = False, **kwargs):
        """Initialize the conversation pane.

        Args:
            conversation_id: The conversation this pane is bound to (required).
            show_header: Whether to show conversation ID header (default False).
                         Set True when switching from history, False for new chats.
        """
        super().__init__(**kwargs)
        self._conversation_id = conversation_id
        self._conversation_history_manager = ConversationHistoryManager()
        self._is_rendered = False  # Track if history has been rendered
        self._show_header = show_header
        self._visualizer: ConversationVisualizer | None = None
        self._is_loading_more = False  # Prevent concurrent loads

        # Content container is the pane itself (not a nested scroll).
        # Messages mount directly to this Container, which flows in main_display.

    def _get_header_text(self) -> str:
        """Get formatted header text with Rich markup (matches splash style)."""
        from openhands_cli.theme import OPENHANDS_THEME
        from openhands_cli.tui.content.splash import format_conversation_header

        return format_conversation_header(
            str(self._conversation_id), prefix="Conversation", theme=OPENHANDS_THEME
        )

    def compose(self) -> ComposeResult:
        # Header with conversation ID (hidden by default, shown for history chats).
        # Uses Rich markup for two-color styling (matches splash).
        header_classes = (
            f"{self.CLASS_PANE_HEADER} {self.CLASS_VISIBLE}"
            if self._show_header
            else self.CLASS_PANE_HEADER
        )
        yield Static(
            self._get_header_text(),
            id=self.ID_HEADER,
            classes=header_classes,
        )
        # Load More button (hidden by default, shown when there's more history).
        yield LoadMoreButton(remaining=0, id=self.ID_LOAD_MORE, classes="-hidden")

    def set_header_visible(self, visible: bool) -> None:
        """Show or hide the conversation ID header dynamically.

        Called when switching to a cached pane to ensure header is visible.
        """
        try:
            header = self.query_one(f"#{self.ID_HEADER}", Static)
            if visible:
                header.add_class(self.CLASS_VISIBLE)
            else:
                header.remove_class(self.CLASS_VISIBLE)
            self._show_header = visible
        except Exception as e:
            logger.debug("Failed to set header visibility: %s", e)

    @property
    def content_container(self) -> Container:
        """Get the content container for this pane (the pane itself)."""
        return self

    @property
    def conversation_id(self) -> uuid.UUID:
        """Get the conversation ID this pane is bound to."""
        return self._conversation_id

    @property
    def is_rendered(self) -> bool:
        """Check if this pane has already rendered its history."""
        return self._is_rendered

    def mark_as_active(self) -> None:
        """Mark pane as having active content (from live input).

        Called when user starts typing in a new conversation.
        Prevents duplicate rendering when switching back to this pane.
        """
        self._is_rendered = True

    @property
    def has_more_history(self) -> bool:
        """Check if there are more events available to load."""
        return self._conversation_history_manager.has_more

    # --- Public API for rendering history ---

    def render_history(
        self,
        events: Sequence[Event],
        visualizer: ConversationVisualizer | None = None,
    ) -> ConversationVisualizer:
        """Render conversation history events.

        Called directly by ConversationSwitcher after pane is mounted.
        If already rendered, skip (use cached content).

        Returns the visualizer (created if not provided).
        """
        # Create visualizer here to ensure pane is fully composed.
        # Importing here to avoid circular imports.
        from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer

        app: OpenHandsApp = self.app  # type: ignore[assignment]
        if visualizer is None:
            visualizer = ConversationVisualizer(
                self.content_container, app, skip_user_messages=True
            )

        # Store visualizer for Load More functionality
        self._visualizer = visualizer

        # Skip if already rendered (use cached content).
        if self._is_rendered:
            return visualizer

        initial_events = self._conversation_history_manager.reset(events)
        if initial_events:
            self._render_events(initial_events, visualizer)
            self.scroll_to_end()

        # Update Load More button visibility
        self._update_load_more_button()

        self._is_rendered = True
        return visualizer

    # --- Message Handler (kept for backward compatibility) ---

    @on(RenderConversationHistory)
    def _on_render_conversation_history(self, event: RenderConversationHistory) -> None:
        """Handle message: render conversation history events."""
        # Only handle messages for our conversation.
        if event.conversation_id != self._conversation_id:
            return

        self.render_history(event.events, event.visualizer)

    def _render_events(
        self,
        events: Sequence[Event],
        visualizer: ConversationVisualizer,
    ) -> None:
        """Render conversation history events to this pane's content container.

        User messages are rendered as Static widgets (matching live input style).
        Other events (actions, observations) are delegated to the visualizer
        which handles action/observation pairing and proper widget creation.
        """
        for event in events:
            widget = self._create_message_widget(event)
            if widget is not None:
                self.content_container.mount(widget)
                continue
            # All other events (actions, observations) go through visualizer.
            visualizer.on_event(event)

    def _create_message_widget(self, event: Event) -> Widget | None:
        """Create a widget for user/assistant messages, or None for other events.

        User messages: Static with "> " prefix.
        Assistant messages: Markdown widget with padding.
        """
        from textual.widgets import Markdown

        if not isinstance(event, MessageEvent):
            return None
        if not event.llm_message:
            return None

        # Extract text content
        text = ""
        if event.llm_message.content:
            for item in event.llm_message.content:
                if hasattr(item, "text"):
                    text += getattr(item, "text", "")
        if not text:
            return None

        role = event.llm_message.role

        if role == "user":
            return Static(f"> {text}", classes="user-message", markup=False)
        elif role == "assistant":
            # Render assistant messages as Markdown with padding
            widget = Markdown(text)
            widget.styles.padding = (0, 0, 0, 3)  # Match agent message padding
            return widget

        return None

    def load_more_history(self, visualizer: ConversationVisualizer) -> None:
        """Load and render the next page of older events (for pagination)."""
        next_events = self._conversation_history_manager.next_page()
        if next_events:
            self._render_events(next_events, visualizer)

    def _update_load_more_button(self) -> None:
        """Update Load More button state based on remaining history."""
        try:
            button = self.query_one(f"#{self.ID_LOAD_MORE}", LoadMoreButton)
            remaining = (
                self._conversation_history_manager._state.remaining_count
                if (self._conversation_history_manager._state)
                else 0
            )
            button.update_remaining(remaining)
        except Exception as e:
            logger.debug("Failed to update load more button: %s", e)

    @on(Button.Pressed, f"#{ID_LOAD_MORE}")
    async def _on_load_more_pressed(self, event: Button.Pressed) -> None:
        """Handle Load More button click: load older events and prepend them."""
        event.stop()

        if self._is_loading_more:
            return  # Prevent concurrent loads
        if not self.has_more_history:
            return
        if not self._visualizer:
            logger.warning("No visualizer available for loading more history")
            return

        self._is_loading_more = True

        try:
            # Get the main_display for scroll position management
            main_display = self.app.query_one("#main_display", VerticalScroll)

            # 1. Save current scroll position and content height
            old_scroll_y = main_display.scroll_y
            old_virtual_height = main_display.virtual_size.height

            # 2. Get next page of events
            next_events = self._conversation_history_manager.next_page()
            if not next_events:
                return

            # 3. Render events and collect the widgets to prepend
            widgets_to_prepend: list[Widget] = []
            for evt in next_events:
                widget = self._create_message_widget(evt)
                if widget is not None:
                    widgets_to_prepend.append(widget)
                else:
                    # Action/observation events go through visualizer
                    # But we need to prepend, not append
                    self._visualizer.on_event(evt)

            # 4. Mount widgets at the correct position (after load more button)
            load_more_btn = self.query_one(f"#{self.ID_LOAD_MORE}", LoadMoreButton)
            for widget in widgets_to_prepend:
                self.mount(widget, after=load_more_btn)

            # 5. Update Load More button
            self._update_load_more_button()

            # 6. Force layout refresh
            self.refresh(layout=True)
            main_display.refresh(layout=True)

            # 7. Wait for layout to complete
            await self.app.animator.wait_for_idle()

            # 8. Adjust scroll position to maintain view
            new_virtual_height = main_display.virtual_size.height
            height_added = new_virtual_height - old_virtual_height
            if height_added > 0:
                new_scroll_y = old_scroll_y + height_added
                main_display.scroll_to(y=new_scroll_y, animate=False, immediate=True)

        except Exception as e:
            logger.error("Failed to load more history: %s", e)
        finally:
            self._is_loading_more = False

    def scroll_to_end(self) -> None:
        """Scroll main_display to show the latest content."""
        try:
            main_display = self.app.query_one("#main_display", VerticalScroll)
            main_display.scroll_end(animate=False)
        except Exception as e:
            logger.debug("Failed to scroll to end: %s", e)
