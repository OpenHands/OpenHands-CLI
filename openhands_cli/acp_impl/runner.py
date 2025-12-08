"""Conversation runner with ACP confirmation support."""

import asyncio
import logging
from typing import TYPE_CHECKING

from openhands.sdk import BaseConversation
from openhands.sdk.conversation.state import (
    ConversationExecutionStatus,
    ConversationState,
)
from openhands.sdk.security.confirmation_policy import (
    ConfirmRisky,
    NeverConfirm,
)
from openhands_cli.acp_impl.confirmation import ask_user_confirmation_acp
from openhands_cli.user_actions.types import UserConfirmation


if TYPE_CHECKING:
    from acp import AgentSideConnection


logger = logging.getLogger(__name__)


class ACPConversationRunner:
    """Handles conversation execution with ACP-style confirmation."""

    def __init__(
        self,
        conversation: BaseConversation,
        conn: "AgentSideConnection",
        session_id: str,
    ):
        """Initialize the ACP conversation runner.

        Args:
            conversation: The conversation to run
            conn: ACP connection for permission requests
            session_id: The session ID
        """
        self.conversation = conversation
        self.conn = conn
        self.session_id = session_id

    async def run_with_confirmation(self) -> None:
        """Run the conversation with confirmation mode enabled.

        This implements similar logic to ConversationRunner._run_with_confirmation
        but adapted for async execution and ACP protocol.
        """
        # If agent was paused at WAITING_FOR_CONFIRMATION, handle it first
        if (
            self.conversation.state.execution_status
            == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
        ):
            user_confirmation = await self._handle_confirmation_request()
            if user_confirmation == UserConfirmation.DEFER:
                return

        while True:
            # Run conversation in a thread (SDK's run() is synchronous)
            await asyncio.to_thread(self.conversation.run)

            # Check execution status
            if (
                self.conversation.state.execution_status
                == ConversationExecutionStatus.FINISHED
            ):
                break

            elif (
                self.conversation.state.execution_status
                == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
            ):
                user_confirmation = await self._handle_confirmation_request()
                if user_confirmation == UserConfirmation.DEFER:
                    return
            elif (
                self.conversation.state.execution_status
                == ConversationExecutionStatus.PAUSED
            ):
                # Agent was paused (e.g., via cancel request)
                logger.info("Conversation paused")
                return
            else:
                # Should not reach here in normal operation
                logger.warning(
                    f"Unexpected execution status: "
                    f"{self.conversation.state.execution_status}"
                )
                break

    async def _handle_confirmation_request(self) -> UserConfirmation:
        """Handle confirmation request via ACP protocol.

        Returns:
            UserConfirmation indicating the user's choice
        """
        # Get pending actions that need confirmation
        pending_actions = ConversationState.get_unmatched_actions(
            self.conversation.state.events
        )
        if not pending_actions:
            logger.debug("No pending actions to confirm")
            return UserConfirmation.ACCEPT

        # Ask for confirmation via ACP
        result = await ask_user_confirmation_acp(
            conn=self.conn,
            session_id=self.session_id,
            pending_actions=pending_actions,
            using_risk_based_policy=isinstance(
                self.conversation.state.confirmation_policy, ConfirmRisky
            ),
        )

        decision = result.decision
        policy_change = result.policy_change

        # Handle user's decision
        if decision == UserConfirmation.REJECT:
            logger.info("User rejected pending actions")
            self.conversation.reject_pending_actions(
                result.reason or "User rejected the actions"
            )
            return decision

        if decision == UserConfirmation.DEFER:
            logger.info("User deferred decision, pausing conversation")
            self.conversation.pause()
            return decision

        # Handle policy changes
        if isinstance(policy_change, NeverConfirm):
            logger.info("User disabled confirmation mode")
            self.conversation.set_confirmation_policy(NeverConfirm())
            # Note: We don't remove security analyzer here as it's set up at
            # conversation creation. The policy change is sufficient.
            return decision

        if isinstance(policy_change, ConfirmRisky):
            logger.info("User enabled risk-based confirmation")
            self.conversation.set_confirmation_policy(policy_change)
            return decision

        # Default: accept
        return decision
