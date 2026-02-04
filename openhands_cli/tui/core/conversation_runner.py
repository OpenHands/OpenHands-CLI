"""Conversation runner with confirmation mode support."""

import asyncio
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from rich.console import Console
from rich.text import Text
from textual.message_pump import MessagePump
from textual.notifications import SeverityLevel

from openhands.sdk import (
    BaseConversation,
    ConversationExecutionStatus,
    Message,
    TextContent,
)
from openhands.sdk.conversation.exceptions import ConversationRunError
from openhands.sdk.conversation.state import (
    ConversationState as SDKConversationState,
)
from openhands.sdk.event.base import Event
from openhands_cli.setup import setup_conversation
from openhands_cli.tui.core.events import ShowConfirmationPanel
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer
from openhands_cli.user_actions.types import UserConfirmation


if TYPE_CHECKING:
    from openhands_cli.tui.core.state import ConversationContainer


class ConversationRunner:
    """Conversation runner with non-blocking confirmation mode support.

    Uses MessagePump to post messages to ConversationManager:
    - ShowConfirmationPanel: Request UI to show confirmation panel
    - Policy changes are handled by ConversationManager

    ConversationContainer is used only for reading state (is_confirmation_active)
    and updating running status.
    """

    def __init__(
        self,
        conversation_id: uuid.UUID,
        state: "ConversationContainer",
        message_pump: MessagePump,
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
            state: ConversationContainer for reading state and updating running status.
            message_pump: MessagePump (ConversationManager) for posting messages.
            notification_callback: Callback for notifications.
            visualizer: Visualizer for output display.
            event_callback: Optional callback for each event.
            env_overrides_enabled: If True, environment variables will override
                stored LLM settings.
            critic_disabled: If True, critic functionality will be disabled.
        """
        self.visualizer = visualizer

        # Create conversation with policy from state
        self.conversation: BaseConversation = setup_conversation(
            conversation_id,
            confirmation_policy=state.confirmation_policy,
            visualizer=visualizer,
            event_callback=event_callback,
            env_overrides_enabled=env_overrides_enabled,
            critic_disabled=critic_disabled,
        )

        self._running = False

        # State for reading (is_confirmation_active) and updating (set_running)
        self._state = state
        # MessagePump for posting messages (ShowConfirmationPanel, etc.)
        self._message_pump = message_pump
        self._notification_callback = notification_callback

    @property
    def is_confirmation_mode_active(self) -> bool:
        return self._state.is_confirmation_active

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
            headless: If True, print status to console
        """
        self.conversation.send_message(message)
        self._execute_conversation(headless=headless)

    def _execute_conversation(
        self,
        decision: UserConfirmation | None = None,
        headless: bool = False,
    ) -> None:
        """Core execution loop - runs conversation and handles confirmation.

        Args:
            decision: User's confirmation decision (if resuming after confirmation)
            headless: If True, print status to console
        """
        if not self.conversation:
            return

        self._update_run_status(True)

        try:
            # Handle user decision if resuming after confirmation
            if decision is not None:
                if decision == UserConfirmation.REJECT:
                    self.conversation.reject_pending_actions(
                        "User rejected the actions"
                    )
                elif decision == UserConfirmation.DEFER:
                    self.conversation.pause()
                    return
                # ACCEPT and policy changes just continue running

            # Run conversation
            if headless:
                console = Console()
                console.print("Agent is working")
                self.conversation.run()
                console.print("Agent finished")
            else:
                self.conversation.run()

            # Check if confirmation needed (only in confirmation mode)
            if (
                self.is_confirmation_mode_active
                and self.conversation.state.execution_status
                == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
            ):
                self._request_confirmation()

        except ConversationRunError as e:
            self._notification_callback("Conversation Error", str(e), "error")
        except Exception as e:
            self._notification_callback(
                "Unexpected Error", f"{type(e).__name__}: {e}", "error"
            )
        finally:
            self._update_run_status(False)

    def _request_confirmation(self) -> None:
        """Post ShowConfirmationPanel message for pending actions."""
        pending_actions = SDKConversationState.get_unmatched_actions(
            self.conversation.state.events
        )
        if pending_actions:
            self._message_pump.post_message(ShowConfirmationPanel(pending_actions))

    async def resume_after_confirmation(self, decision: UserConfirmation) -> None:
        """Resume conversation after user makes a confirmation decision."""
        await asyncio.get_event_loop().run_in_executor(
            None, self._execute_conversation, decision
        )

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
        """Update the running status via ConversationContainer."""
        self._running = is_running
        self._state.set_running(is_running)

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
