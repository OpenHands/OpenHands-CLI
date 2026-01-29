"""ScrollableContent widget for conversation content display.

This module provides ScrollableContent, a VerticalScroll container that
holds conversation content (splash screen and dynamically added messages).

Widget Hierarchy (within ConversationView):
    ConversationView(Container, #conversation_view)
    ├── ScrollableContent(VerticalScroll, #scroll_view)
    │   ├── SplashContent(#splash_content)
    │   └── ... dynamically added conversation widgets
    └── InputAreaContainer(#input_area)  ← docked to bottom
        ├── WorkingStatusLine
        ├── InputField
        └── InfoStatusLine

ScrollableContent handles clearing dynamic content when conversation_id changes
via data_bind() to ConversationView.conversation_id. Message handling
(UserInputSubmitted, SlashCommandSubmitted) is done by ConversationView.
"""

import uuid

from textual.containers import VerticalScroll
from textual.reactive import var


class ScrollableContent(VerticalScroll):
    """Scrollable container for conversation content.

    This widget holds:
    - SplashContent at the top
    - Dynamically added conversation widgets (user messages, agent responses)

    Reactive Properties (via data_bind from ConversationView):
    - conversation_id: Current conversation ID (clears content on change)

    Message handling is done by ConversationView, not by this widget.
    """

    # Reactive property bound via data_bind() to ConversationView
    conversation_id: var[uuid.UUID] = var(uuid.uuid4)

    def watch_conversation_id(self, old_id: uuid.UUID, new_id: uuid.UUID) -> None:
        """Clear dynamic content when conversation changes.

        When conversation_id changes, removes all dynamically added widgets
        (user messages, agent responses, etc.) while preserving:
        - SplashContent (#splash_content) - re-renders via its own binding
        """
        if old_id == new_id:
            return

        # Don't try to clear content if we're not mounted yet
        if not self.is_mounted:
            return

        # Remove all children except splash_content
        for widget in list(self.children):
            if widget.id != "splash_content":
                widget.remove()

        # Scroll to top to show splash screen
        self.scroll_home(animate=False)
