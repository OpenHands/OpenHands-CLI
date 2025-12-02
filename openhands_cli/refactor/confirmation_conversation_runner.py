"""Conversation runner with confirmation mode support for the refactored UI."""

import asyncio
import uuid
from collections.abc import Callable

from openhands.sdk import BaseConversation, Message, TextContent
from openhands.sdk.conversation.state import ConversationExecutionStatus
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmationPolicyBase,
    NeverConfirm,
)
from openhands_cli.refactor.richlog_visualizer import TextualVisualizer
from openhands_cli.setup import setup_conversation
from openhands_cli.user_actions.types import UserConfirmation


class ConfirmationConversationRunner:
    """Conversation runner with confirmation mode support for the refactored UI."""

    def __init__(self, visualizer: TextualVisualizer | None = None):
        """Initialize the conversation runner.

        Args:
            visualizer: Optional visualizer for output display.
        """
        self.conversation: BaseConversation | None = None
        self.conversation_id: uuid.UUID | None = None
        self._running = False
        self.visualizer = visualizer
        self._confirmation_mode_active = False
        self._confirmation_callback: Callable | None = None

    def initialize_conversation(self, include_security_analyzer: bool = False) -> None:
        """Initialize a new conversation.

        Args:
            include_security_analyzer: Whether to include security analyzer for
                confirmation mode.
        """
        self.conversation_id = uuid.uuid4()

        # Setup conversation with or without security analyzer
        self.conversation = setup_conversation(
            self.conversation_id,
            include_security_analyzer=include_security_analyzer,
            visualizer=self.visualizer,
        )

        self._confirmation_mode_active = include_security_analyzer

    @property
    def is_confirmation_mode_active(self) -> bool:
        """Check if confirmation mode is currently active."""
        return self._confirmation_mode_active

    def toggle_confirmation_mode(self) -> None:
        """Toggle confirmation mode on/off."""
        new_confirmation_mode_state = not self._confirmation_mode_active

        # Reinitialize conversation with new confirmation mode state
        if self.conversation_id:
            self.conversation = setup_conversation(
                self.conversation_id,
                include_security_analyzer=new_confirmation_mode_state,
                visualizer=self.visualizer,
            )

        self._confirmation_mode_active = new_confirmation_mode_state

        if new_confirmation_mode_state:
            # Enable confirmation mode: set AlwaysConfirm policy
            self.set_confirmation_policy(AlwaysConfirm())
        else:
            # Disable confirmation mode: set NeverConfirm policy
            self.set_confirmation_policy(NeverConfirm())

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

    async def process_message_async(self, user_input: str) -> None:
        """Process a user message asynchronously to keep UI unblocked.

        Args:
            user_input: The user's message text
        """
        if not self.conversation:
            self.initialize_conversation(
                include_security_analyzer=self._confirmation_mode_active
            )

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
            self.conversation.reject_pending_actions(
                "User rejected the actions"
            )
        elif decision == UserConfirmation.DEFER:
            # Pause the conversation for later resumption
            self.conversation.pause()

        # For ACCEPT, we just continue normally
        return decision

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
