"""Reactive splash widgets that auto-update via data binding.

These widgets bind to AppState's reactive properties (e.g., conversation_id)
and automatically update when the state changes. This eliminates manual
query_one().update() calls when state changes.

AppState.compose() yields these widgets, so data_bind() works because
the active message pump is AppState (the reactive owner).

Example:
    # In AppState.compose():
    yield SplashConversation(id="splash_conversation").data_bind(
        conversation_id=AppState.conversation_id
    )
    
    # When app_state.conversation_id changes, the widget auto-updates
"""

import uuid

from textual.reactive import var
from textual.widgets import Static

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.splash import get_conversation_text


class SplashConversation(Static):
    """Displays the current conversation ID with reactive updates.
    
    Uses data_bind() to bind to AppState.conversation_id. The binding works
    because this widget is yielded from AppState.compose(), where the
    active message pump is AppState itself.
    """

    conversation_id: var[uuid.UUID | None] = var(None)

    def __init__(self, **kwargs) -> None:
        # Set default classes if not provided
        if "classes" not in kwargs:
            kwargs["classes"] = "conversation-panel"
        super().__init__(**kwargs)

    def watch_conversation_id(
        self, _old_value: uuid.UUID | None, new_value: uuid.UUID | None
    ) -> None:
        """Update display when conversation_id changes."""
        if new_value is not None:
            self.update(get_conversation_text(new_value.hex, theme=OPENHANDS_THEME))
        else:
            self.update("")
