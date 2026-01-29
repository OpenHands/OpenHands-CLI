"""Core TUI components including state management and conversation running."""

from openhands_cli.tui.core.conversation_manager import (
    CondenseConversation,
    ConversationManager,
    CreateConversation,
    PauseConversation,
    SendMessage,
    SetConfirmationPolicy,
    SwitchConversation,
)
from openhands_cli.tui.core.state import (
    ConfirmationRequired,
    ConversationFinished,
    ConversationState,
    ConversationView,  # Backward compatibility alias
)


__all__ = [
    # State
    "ConversationState",
    "ConversationView",  # Backward compatibility alias
    "ConversationFinished",
    "ConfirmationRequired",
    # Manager
    "ConversationManager",
    # Messages
    "SendMessage",
    "CreateConversation",
    "SwitchConversation",
    "PauseConversation",
    "CondenseConversation",
    "SetConfirmationPolicy",
]
