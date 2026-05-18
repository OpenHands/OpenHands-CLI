"""Shared confirmation decision handling for ACP and TUI implementations.

This module provides unified logic for handling user confirmation decisions,
reducing duplication between the ACP runner and TUI ConversationRunner.
"""

from openhands.sdk import BaseConversation
from openhands_cli.user_actions.types import UserConfirmation


def handle_confirmation_decision(
    conversation: BaseConversation,
    decision: UserConfirmation,
    reject_reason: str = "User rejected the actions",
) -> None:
    """Handle a user's confirmation decision on the conversation.

    This function applies the decision to the conversation:
    - REJECT: Reject pending actions with the given reason
    - DEFER: Pause the conversation
    - ACCEPT: No action needed (caller continues running)

    Args:
        conversation: The conversation instance to apply the decision to.
        decision: The user's confirmation decision.
        reject_reason: Reason for rejection (used only when decision is REJECT).
    """
    if decision == UserConfirmation.REJECT:
        conversation.reject_pending_actions(reject_reason)
    elif decision == UserConfirmation.DEFER:
        conversation.pause()
    # ACCEPT: no action needed, caller continues running
