"""High-level conversation lifecycle management.

This class coordinates conversation operations:
- Creating new conversations
- Switching between conversations
- Updating conversation metadata
- Posting messages to history panel
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from textual.widgets import Static

from openhands_cli.conversations.models import ConversationMetadata
from openhands_cli.conversations.protocols import ConversationStore
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.splash import get_conversation_text
from openhands_cli.tui.core.conversation_switcher import ConversationSwitcher
from openhands_cli.tui.core.messages import (
    ConversationCreated,
    ConversationTitleUpdated,
)


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


class ConversationManager:
    """Manages conversation lifecycle and coordination.

    This class provides a single point of control for all conversation
    operations, delegating switching logic to ConversationSwitcher.
    """

    def __init__(self, app: OpenHandsApp, store: ConversationStore):
        self.app = app
        self.store = store
        self._switcher = ConversationSwitcher(app)

    @property
    def is_switching(self) -> bool:
        """Check if a conversation switch is in progress."""
        return self._switcher.is_switching

    def switch_to(self, conversation_id: str) -> None:
        """Switch to an existing conversation.

        Args:
            conversation_id: The conversation ID to switch to
        """
        self._switcher.switch_to(conversation_id)

    def create_new(self) -> uuid.UUID | None:
        """Create a new conversation.

        Returns:
            The new conversation ID, or None if creation failed
            (e.g., another conversation is running).
        """
        app = self.app

        # Check if a conversation is currently running
        if app.conversation_runner and app.conversation_runner.is_running:
            app.notify(
                title="New Conversation Error",
                message="Cannot start a new conversation while one is running. "
                "Please wait for the current conversation to complete or pause it.",
                severity="error",
            )
            return None

        # Create a new conversation via store
        new_id_str = self.store.create()
        new_id = uuid.UUID(new_id_str)

        # Update active conversation
        app.conversation_id = new_id
        app.conversation_session_manager.set_active_conversation(new_id)

        # Reset the conversation runner
        app.conversation_runner = None

        # Remove any existing confirmation panel
        if app.confirmation_panel:
            app.confirmation_panel.remove()
            app.confirmation_panel = None

        # Hide all existing panes before showing splash
        app._hide_all_panes()

        # Show system splash for new conversations (don't create pane yet -
        # it will be created when user types first message)
        app._set_splash_visible(True)

        # Update splash conversation widget with new ID
        splash_conversation = app.query_one("#splash_conversation", Static)
        splash_conversation.update(
            get_conversation_text(new_id.hex, theme=OPENHANDS_THEME)
        )

        # Notify app about creation (App will propagate to history panel)
        app.post_message(ConversationCreated(new_id))

        # Scroll to top to show the splash screen
        app.main_display.scroll_home(animate=False)

        # Notify user
        app.notify(
            title="New Conversation",
            message="Started a new conversation",
            severity="information",
        )

        return new_id

    def update_title(self, title: str) -> None:
        """Update the current conversation's title in the history panel.

        Args:
            title: The new title (typically the first user message)
        """
        self.app.post_message(ConversationTitleUpdated(self.app.conversation_id, title))

    def list_conversations(self, limit: int = 100) -> list[ConversationMetadata]:
        """List conversations from the store."""
        return self.store.list_conversations(limit=limit)
