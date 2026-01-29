"""Conversation runner with confirmation mode support."""

import asyncio
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from rich.console import Console
from rich.text import Text
from textual.notifications import SeverityLevel

from openhands.sdk import (
    BaseConversation,
    ConversationExecutionStatus,
    Message,
    TextContent,
)
from openhands.sdk.conversation.exceptions import ConversationRunError
from openhands.sdk.conversation.state import (
    ConversationState,
)
from openhands.sdk.event.base import Event
from openhands.sdk.security.confirmation_policy import (
    ConfirmRisky,
    NeverConfirm,
)
from openhands_cli.setup import setup_conversation
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer
from openhands_cli.user_actions.types import UserConfirmation


if TYPE_CHECKING:
    from openhands_cli.tui.core.state import ConversationView


class ConversationRunner:
    """Conversation runner with confirmation mode support.

    ConversationView owns the confirmation policy. This class delegates policy
    operations to ConversationView rather than managing policy state internally.
    """

    def __init__(
        self,
        conversation_id: uuid.UUID,
        conversation_view: "ConversationView",
        confirmation_callback: Callable,
        notification_callback: Callable[[str, str, SeverityLevel], None],
        visualizer: ConversationVisualizer,
        event_callback: Callable[[Event], None] | None = None,
        *,
        env_overrides_enabled: bool = False,
        critic_disabled: bool = False,
    ):
        """Initialize the conversation runner.

        Args:
            conversation_id: UUID for the conversation.
            conversation_view: ConversationView for reactive state updates.
                Owns confirmation policy and syncs it to conversation.
            confirmation_callback: Callback for handling action confirmations.
            notification_callback: Callback for notifications.
            visualizer: Visualizer for output display.
            event_callback: Optional callback for each event.
            env_overrides_enabled: If True, environment variables will override
                stored LLM settings.
            critic_disabled: If True, critic functionality will be disabled.
        """
        self.visualizer = visualizer

        # Create conversation with policy from ConversationView
        self.conversation: BaseConversation = setup_conversation(
            conversation_id,
            confirmation_policy=conversation_view.confirmation_policy,
            visualizer=visualizer,
            event_callback=event_callback,
            env_overrides_enabled=env_overrides_enabled,
            critic_disabled=critic_disabled,
        )

        self._running = False

        # State management via ConversationView (which owns the confirmation policy)
        self._conversation_view = conversation_view
        self._confirmation_callback = confirmation_callback
        self._notification_callback = notification_callback

        # Attach conversation to ConversationView - this syncs the policy
        self._conversation_view.attach_conversation(self.conversation)

    @property
    def is_confirmation_mode_active(self) -> bool:
        return self._conversation_view.is_confirmation_active

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

    async def process_message_async(
        self, user_input: str, headless: bool = False
    ) -> None:
        """Process a user message asynchronously to keep UI unblocked.

        Args:
            user_input: The user's message text
        """
        # Create message from user input
        message = Message(
            role="user",
            content=[TextContent(text=user_input)],
        )

        # Run conversation processing in a separate thread to avoid blocking UI
        await asyncio.get_event_loop().run_in_executor(
            None, self._run_conversation_sync, message, headless
        )

    def _run_conversation_sync(self, message: Message, headless: bool = False) -> None:
        """Run the conversation synchronously in a thread.

        Args:
            message: The message to process
        """
        self._update_run_status(True)

        try:
            # Send message and run conversation
            self.conversation.send_message(message)
            if self.is_confirmation_mode_active:
                self._run_with_confirmation()
            elif headless:
                console = Console()
                console.print("Agent is working")
                self.conversation.run()
                console.print("Agent finished")
            else:
                self.conversation.run()

        except ConversationRunError as e:
            # Handle conversation run errors (includes LLM errors)
            self._notification_callback("Conversation Error", str(e), "error")
        except Exception as e:
            # Handle any other unexpected errors
            self._notification_callback(
                "Unexpected Error", f"{type(e).__name__}: {e}", "error"
            )
        finally:
            self._update_run_status(False)

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
            # Accept actions and change policy to NeverConfirm via ConversationView
            self._conversation_view.set_confirmation_policy(NeverConfirm())
        elif decision == UserConfirmation.CONFIRM_RISKY:
            # Accept actions and change policy to ConfirmRisky via ConversationView
            self._conversation_view.set_confirmation_policy(ConfirmRisky())

        # For ACCEPT and policy-changing decisions, we continue normally
        return decision

    @property
    def is_running(self) -> bool:
        """Check if conversation is currently running."""
        return self._running

    async def pause(self) -> None:
        """Pause the running conversation."""
        if self._running:
            self._notification_callback(
                "Pausing conversation",
                "Pausing conversation, this make take a few seconds...",
                "information",
            )
            await asyncio.to_thread(self.conversation.pause)
        else:
            self._notification_callback(
                "No running converastion", "No running conversation to pause", "warning"
            )

    async def condense_async(self) -> None:
        """Condense the conversation history asynchronously."""
        if self._running:
            self._notification_callback(
                "Condense Error",
                "Cannot condense while conversation is running.",
                "warning",
            )
            return

        try:
            # Notify user that condensation is starting
            self._notification_callback(
                "Condensation Started",
                "Conversation condensation will be completed shortly...",
                "information",
            )

            # Run condensation in a separate thread to avoid blocking UI
            await asyncio.to_thread(self.conversation.condense)

            # Notify user of successful completion
            self._notification_callback(
                "Condensation Complete",
                "Conversation history has been condensed successfully",
                "information",
            )
        except Exception as e:
            # Notify user of error
            self._notification_callback(
                "Condensation Error",
                f"Failed to condense conversation: {str(e)}",
                "error",
            )

    def _update_run_status(self, is_running: bool) -> None:
        """Update the running status via ConversationView."""
        self._running = is_running
        self._conversation_view.set_running(is_running)

    def pause_runner_without_blocking(self):
        if self.is_running:
            asyncio.create_task(self.pause())

    def get_conversation_summary(self) -> tuple[int, Text]:
        """Get a summary of the conversation for headless mode output.

        Returns:
            Dictionary with conversation statistics and last agent message
        """
        if not self.conversation or not self.conversation.state:
            return 0, Text(
                text="No conversation data available",
            )

        agent_event_count = 0
        last_agent_message = Text(text="No agent messages found")

        # Parse events to count messages
        for event in self.conversation.state.events:
            if event.source == "agent":
                agent_event_count += 1
                last_agent_message = event.visualize

        return agent_event_count, last_agent_message
