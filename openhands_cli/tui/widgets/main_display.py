"""ScrollableContent widget for conversation content display.

This module provides ScrollableContent, a VerticalScroll container that
holds conversation content (splash screen and dynamically added messages).

Widget Hierarchy (within ConversationContainer):
    ConversationContainer(Container, #conversation_state)
    ├── ScrollableContent(VerticalScroll, #scroll_view)
    │   ├── SplashContent(#splash_content)
    │   ├── ... dynamically added conversation widgets
    │   └── InlineConfirmationPanel (when pending_action_count > 0)
    └── InputAreaContainer(#input_area)  ← docked to bottom
        ├── WorkingStatusLine
        ├── InputField
        └── InfoStatusLine

ScrollableContent handles:
- Clearing dynamic content when conversation_id changes
- Mounting InlineConfirmationPanel when pending_action_count becomes > 0

Message handling (UserInputSubmitted) is done by ConversationManager.
"""

import uuid

from textual.containers import VerticalScroll
from textual.reactive import var


class ScrollableContent(VerticalScroll):
    """Scrollable container for conversation content.

    This widget holds:
    - SplashContent at the top
    - Dynamically added conversation widgets (user messages, agent responses)
    - InlineConfirmationPanel (when waiting for user confirmation)

    Reactive Properties (via data_bind from ConversationContainer):
    - conversation_id: Current conversation ID (clears content on change)
    - pending_action_count: Number of actions awaiting confirmation (>0 mounts panel)

    Message handling is done by ConversationManager, not by this widget.
    """

    # Reactive properties bound via data_bind() to ConversationContainer
    conversation_id: var[uuid.UUID | None] = var(None)
    pending_action_count: var[int] = var(0)

    def watch_conversation_id(
        self, old_id: uuid.UUID | None, new_id: uuid.UUID | None
    ) -> None:
        """Clear dynamic content when conversation changes.

        Clears dynamically added widgets (preserving SplashContent) when:
        - Switch starts: old_id=UUID -> new_id=None
        - New conversation: old_id=UUID -> new_id=different UUID
        """
        if old_id == new_id:
            return

        if not self.is_mounted:
            return

        # Clear widgets when leaving a conversation (old_id was a valid UUID)
        if old_id is not None:
            for widget in list(self.children):
                if widget.id != "splash_content":
                    widget.remove()
            self.scroll_home(animate=False)

    def watch_pending_action_count(self, old_count: int, new_count: int) -> None:
        """Mount InlineConfirmationPanel when pending_action_count becomes > 0.

        When count goes from 0 to >0, mounts the confirmation panel.
        The panel removes itself when user makes a selection.
        """
        if not self.is_mounted:
            return

        # Mount panel when transitioning from 0 to >0
        if old_count == 0 and new_count > 0:
            from openhands_cli.tui.panels.confirmation_panel import (
                InlineConfirmationPanel,
            )

            self.mount(InlineConfirmationPanel(new_count))
            self.scroll_end(animate=False)
