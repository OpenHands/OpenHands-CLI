"""Confirmation mode implementation for ACP."""

import logging
from collections.abc import Callable
from typing import Literal

from acp import Client
from acp.schema import (
    AllowedOutcome,
    PermissionOption,
    SessionMode,
    ToolCallUpdate,
)

from openhands.sdk.event import ActionEvent
from openhands.sdk.security.confirmation_policy import ConfirmRisky, NeverConfirm
from openhands.sdk.security.risk import SecurityRisk
from openhands_cli.user_actions.types import ConfirmationResult, UserConfirmation


logger = logging.getLogger(__name__)


# Type alias for confirmation modes
ConfirmationMode = Literal["always-ask", "always-approve", "llm-approve"]


# Confirmation mode descriptions
CONFIRMATION_MODES: dict[ConfirmationMode, dict[str, str]] = {
    "always-ask": {
        "short": "Ask for permission before every action",
        "long": "Agent will ask for permission before executing every action.",
    },
    "always-approve": {
        "short": "Automatically approve all actions",
        "long": (
            "Agent will automatically approve all actions without asking. "
            "⚠️  Use with caution!"
        ),
    },
    "llm-approve": {
        "short": "Use LLM security analyzer to auto-approve safe actions",
        "long": (
            "Agent will use LLM security analyzer to automatically "
            "approve safe actions. You will only be asked for permission "
            "on potentially risky actions."
        ),
    },
}


# Permission options for confirmation requests
PERMISSION_OPTIONS = [
    PermissionOption(
        option_id="accept",
        name="Yes, proceed",
        kind="allow_once",
    ),
    PermissionOption(
        option_id="reject",
        name="Reject",
        kind="reject_once",
    ),
    PermissionOption(
        option_id="always_proceed",
        name="Always proceed (don't ask again)",
        kind="allow_always",
    ),
    PermissionOption(
        option_id="risk_based",
        name="Auto-confirm LOW/MEDIUM risk, ask for HIGH risk action",
        kind="allow_once",
    ),
]


def get_available_modes() -> list[SessionMode]:
    """Get list of available session modes.

    Returns:
        List of SessionMode objects representing available modes
    """
    return [
        SessionMode(
            id="always-ask",
            name="Always Ask Mode",
            description="Request permission before making any changes",
        ),
        SessionMode(
            id="always-approve",
            name="Always Approve Mode",
            description="Automatically approve all actions without asking",
        ),
        SessionMode(
            id="llm-approve",
            name="LLM Approve Mode",
            description=(
                "Use LLM security analyzer to auto-approve safe actions. "
                "Only ask for permission on high risk actions."
            ),
        ),
    ]


# Dispatch dictionary for handling user choices
def _get_option_handlers() -> dict[str, Callable[[], ConfirmationResult]]:
    """Get handlers for each permission option.

    Returns:
        Dictionary mapping option IDs to handler functions
    """
    return {
        "accept": lambda: ConfirmationResult(decision=UserConfirmation.ACCEPT),
        "reject": lambda: ConfirmationResult(
            decision=UserConfirmation.REJECT,
            reason=(
                "User rejected the action. Please ask the user how "
                "they want to proceed."
            ),
        ),
        "always_proceed": lambda: ConfirmationResult(
            decision=UserConfirmation.ACCEPT,
            policy_change=NeverConfirm(),
        ),
        "risk_based": lambda: ConfirmationResult(
            decision=UserConfirmation.ACCEPT,
            policy_change=ConfirmRisky(threshold=SecurityRisk.HIGH),
        ),
    }


async def ask_user_confirmation_acp(
    conn: Client,
    session_id: str,
    pending_actions: list[ActionEvent],
) -> ConfirmationResult:
    """Ask user to confirm pending actions via ACP protocol.

    Args:
        conn: ACP connection for sending permission requests
        session_id: The session ID
        pending_actions: List of pending actions from the agent

    Returns:
        ConfirmationResult with decision, optional policy_change, and reason
    """
    if not pending_actions:
        return ConfirmationResult(decision=UserConfirmation.ACCEPT)

    # Build description of actions
    actions_description = []
    for i, action in enumerate(pending_actions, 1):
        tool_name = action.tool_name
        action_content = (
            str(action.action.visualize) if action.action else "[unknown action]"
        )
        actions_description.append(f"{i}. {tool_name}: {action_content}...")

    # Create a tool call representation
    tool_call = ToolCallUpdate(
        tool_call_id=f"confirmation-{session_id}",
        title="Confirm Agent Actions",
        status="pending",
        kind="other",
    )

    # Send permission request
    try:
        response = await conn.request_permission(
            session_id=session_id, tool_call=tool_call, options=PERMISSION_OPTIONS
        )

        outcome = response.outcome

        # Handle DeniedOutcome - user cancelled
        if not isinstance(outcome, AllowedOutcome):
            return ConfirmationResult(
                decision=UserConfirmation.REJECT,
                reason=(
                    "User cancelled the action. Please ask the user how "
                    "they want to proceed."
                ),
            )

        # Handle AllowedOutcome using dispatch dictionary
        option_handlers = _get_option_handlers()
        handler = option_handlers.get(outcome.optionId)

        if handler:
            return handler()

        # Unknown option - treat as reject
        logger.warning(
            f"Unknown option selected: {outcome.optionId}, treating as reject"
        )
        return ConfirmationResult(decision=UserConfirmation.REJECT)

    except Exception as e:
        logger.error(f"Error during ACP confirmation: {e}", exc_info=True)
        # If confirmation fails, defer (pause) rather than accepting or rejecting
        return ConfirmationResult(decision=UserConfirmation.DEFER)
