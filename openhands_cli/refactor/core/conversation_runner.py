"""Conversation runner with confirmation mode support for the refactored UI."""

import asyncio
import uuid
from collections.abc import Callable

from openhands.sdk import BaseConversation, Message, TextContent
from openhands.sdk.conversation.exceptions import ConversationRunError
from openhands.sdk.conversation.state import ConversationExecutionStatus
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmationPolicyBase,
    ConfirmRisky,
    NeverConfirm,
)
from openhands_cli.refactor.widgets.richlog_visualizer import TextualVisualizer
from openhands_cli.setup import setup_conversation
from openhands_cli.user_actions.types import UserConfirmation


class ConversationRunner:
    """Conversation runner with confirmation mode support for the refactored UI."""

    def __init__(
        self,
        conversation_id: uuid.UUID,
        error_callback: Callable[[str, str], None],
        visualizer: TextualVisualizer | None = None,
        initial_confirmation_policy: ConfirmationPolicyBase | None = None,
    ):
        """Initialize the conversation runner.

        Args:
            conversation_id: UUID for the conversation.
            error_callback: Callback for handling errors.
                          Should accept (error_title: str, error_message: str).
            visualizer: Optional visualizer for output display.
            initial_confirmation_policy: Initial confirmation policy to use.
                                        If None, defaults to AlwaysConfirm.
        """
        self.conversation: BaseConversation | None = None
        self.conversation_id: uuid.UUID = conversation_id
        self._running = False
        self.visualizer = visualizer
        self.initial_confirmation_policy = (
            initial_confirmation_policy or AlwaysConfirm()
        )
        # Set confirmation mode state based on initial policy
        self._confirmation_mode_active = not isinstance(
            self.initial_confirmation_policy, NeverConfirm
        )
        self._confirmation_callback: Callable | None = None
        self._error_callback: Callable[[str, str], None] = error_callback

    @property
    def is_confirmation_mode_active(self) -> bool:
        """Check if confirmation mode is currently active."""
        return self._confirmation_mode_active

    def toggle_confirmation_mode(self) -> None:
        """Toggle confirmation mode on/off."""
        new_confirmation_mode_state = not self._confirmation_mode_active

        # Choose confirmation policy based on new state
        if new_confirmation_mode_state:
            confirmation_policy = AlwaysConfirm()
        else:
            confirmation_policy = NeverConfirm()

        # Use the centralized method to change policy and update state
        self._change_confirmation_policy(confirmation_policy)

    def set_confirmation_policy(
        self, confirmation_policy: ConfirmationPolicyBase
    ) -> None:
        """Set the confirmation policy for the conversation."""
        if self.conversation:
            self.conversation.set_confirmation_policy(confirmation_policy)

    def set_confirmation_callback(self, callback: Callable) -> None:
        """Set the callback function for handling confirmation requests.

        Args:
            callback: Function that will be called when confirmation is needed.
                     Should return UserConfirmation decision.
        """
        self._confirmation_callback = callback

    async def queue_message(self, user_input: str) -> None:
        """Queue a message for a running conversation"""
        assert self.conversation is not None, "Conversation should be running"
        assert user_input
        message = Message(
            role="user",
            content=[TextContent(text=user_input)],
        )

        # This doesn't block - it just adds the message to the queue
        # The running conversation will process it when ready
        loop = asyncio.get_running_loop()
        # Run send_message in the same thread pool, not on the UI loop
        await loop.run_in_executor(None, self.conversation.send_message, message)

    def initialize_conversation(
        self,
        include_security_analyzer: bool | None = None,
    ) -> None:
        """Initialize a new conversation.

        Args:
            include_security_analyzer: Whether to include security analyzer for
                confirmation mode. If None, uses the initial confirmation policy
                provided in the constructor.
        """

        # Choose confirmation policy
        if include_security_analyzer is not None:
            # Legacy behavior: use the boolean parameter
            if include_security_analyzer:
                confirmation_policy = AlwaysConfirm()
            else:
                confirmation_policy = NeverConfirm()
            self._confirmation_mode_active = include_security_analyzer
        else:
            # Use the initial confirmation policy from constructor
            confirmation_policy = self.initial_confirmation_policy
            # Confirmation mode state was already set in constructor

        # Setup conversation with proper parameters
        self.conversation = setup_conversation(
            self.conversation_id,
            confirmation_policy=confirmation_policy,
            visualizer=self.visualizer,
        )

    async def process_message_async(self, user_input: str) -> None:
        """Process a user message asynchronously to keep UI unblocked.

        Args:
            user_input: The user's message text
        """
        if not self.conversation:
            self.initialize_conversation()

        # Create message from user input
        message = Message(
            role="user",
            content=[TextContent(text=user_input)],
        )

        # Run conversation processing in a separate thread to avoid blocking UI
        await asyncio.get_event_loop().run_in_executor(
            None, self._run_conversation_sync, message
        )

    def _run_conversation_sync(self, message: Message) -> None:
        """Run the conversation synchronously in a thread.

        Args:
            message: The message to process
        """
        if not self.conversation:
            return

        self._running = True
        try:
            # Send message and run conversation
            self.conversation.send_message(message)

            if self._confirmation_mode_active:
                self._run_with_confirmation()
            else:
                self.conversation.run()
        except ConversationRunError as e:
            # Handle conversation run errors (includes LLM errors)
            self._handle_conversation_error(e)
        except Exception as e:
            # Handle any other unexpected errors
            self._handle_unexpected_error(e)
        finally:
            self._running = False

    def _run_with_confirmation(self) -> None:
        """Run conversation with confirmation mode enabled."""
        if not self.conversation:
            return

        # If agent was paused, resume with confirmation request
        if (
            self.conversation.state.execution_status
            == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
        ):
            user_confirmation = self._handle_confirmation_request()
            if user_confirmation == UserConfirmation.DEFER:
                return

        while True:
            self.conversation.run()

            # In confirmation mode, agent either finishes or waits for user confirmation
            if (
                self.conversation.state.execution_status
                == ConversationExecutionStatus.FINISHED
            ):
                break

            elif (
                self.conversation.state.execution_status
                == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
            ):
                user_confirmation = self._handle_confirmation_request()
                if user_confirmation == UserConfirmation.DEFER:
                    return
            else:
                # For other states, break to avoid infinite loop
                break

    def _handle_confirmation_request(self) -> UserConfirmation:
        """Handle confirmation request from user.

        Returns:
            UserConfirmation indicating the user's choice
        """
        if not self.conversation:
            return UserConfirmation.DEFER

        # Get pending actions that need confirmation
        from openhands.sdk.conversation.state import ConversationState

        pending_actions = ConversationState.get_unmatched_actions(
            self.conversation.state.events
        )

        if not pending_actions:
            return UserConfirmation.ACCEPT

        # Get user decision through callback
        if self._confirmation_callback:
            decision = self._confirmation_callback(pending_actions)
        else:
            # Default to accepting if no callback is set
            decision = UserConfirmation.ACCEPT

        # Handle the user's decision
        if decision == UserConfirmation.REJECT:
            # Reject pending actions - this creates UserRejectObservation events
            self.conversation.reject_pending_actions("User rejected the actions")
        elif decision == UserConfirmation.DEFER:
            # Pause the conversation for later resumption
            self.conversation.pause()
        elif decision == UserConfirmation.ALWAYS_PROCEED:
            # Accept actions and change policy to NeverConfirm
            self._change_confirmation_policy(NeverConfirm())
        elif decision == UserConfirmation.CONFIRM_RISKY:
            # Accept actions and change policy to ConfirmRisky
            self._change_confirmation_policy(ConfirmRisky())

        # For ACCEPT and policy-changing decisions, we continue normally
        return decision

    def _change_confirmation_policy(self, new_policy: ConfirmationPolicyBase) -> None:
        """Change the confirmation policy and update internal state.

        Args:
            new_policy: The new confirmation policy to set
        """
        if self.conversation:
            self.conversation.set_confirmation_policy(new_policy)

        # Update internal state based on the policy type
        if isinstance(new_policy, NeverConfirm):
            self._confirmation_mode_active = False
        else:
            self._confirmation_mode_active = True

    @property
    def is_running(self) -> bool:
        """Check if conversation is currently running."""
        return self._running

    @property
    def current_conversation_id(self) -> str | None:
        """Get the current conversation ID as a string."""
        return str(self.conversation_id) if self.conversation_id else None

    def pause(self) -> None:
        """Pause the running conversation."""
        if self.conversation and self._running:
            self.conversation.pause()

    def _handle_conversation_error(self, error: ConversationRunError) -> None:
        """Handle conversation run errors by passing them to the error callback.

        Args:
            error: The ConversationRunError that occurred
        """
        self._error_callback("Conversation Error", str(error))

    def _handle_unexpected_error(self, error: Exception) -> None:
        """Handle unexpected errors by passing them to the error callback.

        Args:
            error: The unexpected exception that occurred
        """
        self._error_callback("Unexpected Error", f"{type(error).__name__}: {error}")
