"""Core TUI components including state management and conversation running."""

from openhands_cli.tui.core.conversation_manager import (
    CondenseConversation,
    ConversationManager,
    CreateConversation,
    PauseConversation,
    SendMessage,
    SetConfirmationPolicy,
    SwitchConfirmed,
    SwitchConversation,
)
from openhands_cli.tui.core.events import (
    ConfirmationDecision,
    RequestSwitchConfirmation,
    ShowConfirmationPanel,
)
from openhands_cli.tui.core.state import (
    ConfirmationRequired,
    ConversationContainer,
    ConversationFinished,
)


__all__ = [
    # Container (UI component that owns reactive state)
    "ConversationContainer",
    "ConversationFinished",
    "ConfirmationRequired",
    # Manager
    "ConversationManager",
    # Operation Messages (input to ConversationManager)
    "SendMessage",
    "CreateConversation",
    "SwitchConversation",
    "PauseConversation",
    "CondenseConversation",
    "SetConfirmationPolicy",
    "SwitchConfirmed",
    # Events (App ↔ ConversationManager)
    "RequestSwitchConfirmation",
    "ShowConfirmationPanel",
    "ConfirmationDecision",
]
