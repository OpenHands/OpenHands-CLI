"""Core TUI components including state management and conversation running."""

from openhands_cli.tui.core.state import (
    AppState,
    ConfirmationRequired,
    ConversationFinished,
    StateManager,  # Backwards compatibility alias for AppState
)


__all__ = [
    "AppState",
    "ConversationFinished",
    "ConfirmationRequired",
    "StateManager",  # Backwards compatibility alias
]
