"""Confirmation mode implementation for ACP."""

import logging
from typing import TYPE_CHECKING

from acp.schema import (
    AllowedOutcome,
    PermissionOption,
    RequestPermissionRequest,
    ToolCallUpdate,
)

from openhands.sdk.security.confirmation_policy import (
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.risk import SecurityRisk
from openhands_cli.user_actions.types import ConfirmationResult, UserConfirmation


if TYPE_CHECKING:
    from acp import AgentSideConnection


logger = logging.getLogger(__name__)


async def ask_user_confirmation_acp(
    conn: "AgentSideConnection",
    session_id: str,
    pending_actions: list,
    using_risk_based_policy: bool = False,
) -> ConfirmationResult:
    """Ask user to confirm pending actions via ACP protocol.

    Args:
        conn: ACP connection for sending permission requests
        session_id: The session ID
        pending_actions: List of pending actions from the agent
        using_risk_based_policy: Whether risk-based policy is already enabled

    Returns:
        ConfirmationResult with decision, optional policy_change, and reason
    """
    if not pending_actions:
        return ConfirmationResult(decision=UserConfirmation.ACCEPT)

    # Build description of actions
    actions_description = []
    for i, action in enumerate(pending_actions, 1):
        tool_name = getattr(action, "tool_name", "[unknown tool]")
        action_content = (
            str(getattr(action, "action", ""))[:100].replace("\n", " ")
            or "[unknown action]"
        )
        actions_description.append(f"{i}. {tool_name}: {action_content}...")

    description = (
        f"Agent created {len(pending_actions)} action(s) and is waiting for "
        f"confirmation:\n\n" + "\n".join(actions_description)
    )

    # Build permission options
    options = [
        PermissionOption(
            optionId="accept",
            name="Yes, proceed",
            kind="allow_once",
        ),
        PermissionOption(
            optionId="reject",
            name="Reject",
            kind="reject_once",
        ),
        PermissionOption(
            optionId="always_proceed",
            name="Always proceed (don't ask again)",
            kind="allow_always",
        ),
    ]

    if not using_risk_based_policy:
        options.append(
            PermissionOption(
                optionId="risk_based",
                name="Auto-confirm LOW/MEDIUM risk, ask for HIGH risk",
                kind="allow_once",
            )
        )

    # Create a tool call representation
    tool_call = ToolCallUpdate(
        toolCallId=f"confirmation-{session_id}",
        title="Confirm Agent Actions",
        status="pending",
        kind="other",
    )

    # Send permission request
    try:
        response = await conn.requestPermission(
            RequestPermissionRequest(
                sessionId=session_id,
                toolCall=tool_call,
                options=options,
            )
        )

        # Handle user's choice
        outcome = response.outcome
        if isinstance(outcome, AllowedOutcome):
            selected = outcome.optionId
            if selected == "accept":
                return ConfirmationResult(decision=UserConfirmation.ACCEPT)
            elif selected == "reject":
                # For reject, we could ask for a reason via another permission request
                # For now, just return reject without reason
                return ConfirmationResult(
                    decision=UserConfirmation.REJECT,
                    reason="User rejected via ACP",
                )
            elif selected == "always_proceed":
                return ConfirmationResult(
                    decision=UserConfirmation.ACCEPT,
                    policy_change=NeverConfirm(),
                )
            elif selected == "risk_based":
                return ConfirmationResult(
                    decision=UserConfirmation.ACCEPT,
                    policy_change=ConfirmRisky(threshold=SecurityRisk.HIGH),
                )
            else:
                logger.warning(
                    f"Unknown option selected: {selected}, treating as reject"
                )
                return ConfirmationResult(decision=UserConfirmation.REJECT)
        else:
            # DeniedOutcome - user cancelled
            return ConfirmationResult(
                decision=UserConfirmation.REJECT, reason="User cancelled via ACP"
            )

    except Exception as e:
        logger.error(f"Error during ACP confirmation: {e}", exc_info=True)
        # If confirmation fails, defer (pause) rather than accepting or rejecting
        return ConfirmationResult(decision=UserConfirmation.DEFER)
