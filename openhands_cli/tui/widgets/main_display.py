"""ScrollableContent widget for conversation content display.

This module provides ScrollableContent, a VerticalScroll container that
holds conversation content (splash screen and dynamically added messages).

Widget Hierarchy (within ConversationState):
    ConversationState(Container, #conversation_state)
    ├── ScrollableContent(VerticalScroll, #scroll_view)
    │   ├── SplashContent(#splash_content)
    │   └── ... dynamically added conversation widgets
    └── InputAreaContainer(#input_area)  ← docked to bottom
        ├── WorkingStatusLine
        ├── InputField
        └── InfoStatusLine

ScrollableContent handles clearing dynamic content when conversation_id changes
via data_bind() to ConversationState.conversation_id. Message handling
(UserInputSubmitted) is done by ConversationManager.
"""

import uuid

from textual.containers import VerticalScroll
from textual.reactive import var


class ScrollableContent(VerticalScroll):
    """Scrollable container for conversation content.

    This widget holds:
    - SplashContent at the top
    - Dynamically added conversation widgets (user messages, agent responses)

    Reactive Properties (via data_bind from ConversationState):
    - conversation_id: Current conversation ID (clears content on change)

    Message handling is done by ConversationManager, not by this widget.
    """

    # Reactive property bound via data_bind() to ConversationState
    # None indicates switching in progress
    conversation_id: var[uuid.UUID | None] = var(None)

    def watch_conversation_id(
        self, old_id: uuid.UUID | None, new_id: uuid.UUID | None
    ) -> None:
        """Clear dynamic content when conversation changes.

        When conversation_id changes to a new UUID, removes all dynamically
        added widgets (user messages, agent responses, etc.) while preserving:
        - SplashContent (#splash_content) - re-renders via its own binding

        Skips if new_id is None (switching in progress).
        """
        if old_id == new_id:
            return

        # Skip during switch (conversation_id = None)
        if new_id is None:
            return

        # Don't try to clear content if we're not mounted yet
        if not self.is_mounted:
            return

        # Skip clearing if this is initial load (old was None from var default)
        # In that case, just let the content render naturally
        if old_id is None:
            return

        # New/different conversation - clear and show splash
        for widget in list(self.children):
            if widget.id != "splash_content":
                widget.remove()

        self.scroll_home(animate=False)
