"""Shared helpers for conversation execution status checks."""

from openhands.sdk import BaseConversation, ConversationExecutionStatus


def is_waiting_for_confirmation(conversation: BaseConversation) -> bool:
    """Check if conversation is waiting for user confirmation."""
    return (
        conversation.state.execution_status
        == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
    )


def is_finished(conversation: BaseConversation) -> bool:
    """Check if conversation execution has finished."""
    return conversation.state.execution_status == ConversationExecutionStatus.FINISHED


def is_paused(conversation: BaseConversation) -> bool:
    """Check if conversation is paused."""
    return conversation.state.execution_status == ConversationExecutionStatus.PAUSED
