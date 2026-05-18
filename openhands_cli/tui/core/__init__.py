"""Core TUI components including state management and conversation running."""

from openhands_cli.tui.core.conversation_manager import (
    CondenseConversation,
    ConversationManager,
    CreateConversation,
    PauseConversation,
    SetAgentMode,
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
    AgentMode,
    ConfirmationRequired,
    ConversationContainer,
    ConversationFinished,
)
from openhands_cli.tui.messages import SendMessage


__all__ = [
    # Container (UI component that owns reactive state)
    "ConversationContainer",
    "ConversationFinished",
    "ConfirmationRequired",
    # Types
    "AgentMode",
    # Manager
    "ConversationManager",
    # Operation Messages (input to ConversationManager)
    "SendMessage",
    "CreateConversation",
    "SwitchConversation",
    "PauseConversation",
    "CondenseConversation",
    "SetConfirmationPolicy",
    "SetAgentMode",
    "SwitchConfirmed",
    # Events (App ↔ ConversationManager)
    "RequestSwitchConfirmation",
    "ShowConfirmationPanel",
    "ConfirmationDecision",
]
