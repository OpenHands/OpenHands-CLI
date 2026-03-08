"""Conversation runner with confirmation mode support."""

import asyncio
import logging
import time
import uuid
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
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
from openhands.sdk.event.condenser import Condensation
from openhands_cli.setup import setup_conversation
from openhands_cli.tui.core.events import ShowConfirmationPanel
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer
from openhands_cli.user_actions.types import UserConfirmation


if TYPE_CHECKING:
    from openhands_cli.tui.core.state import ConversationContainer


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplayPlan:
    summary_text: str | None
    tail_events: list[Event]
    total_count: int
    hidden_count: int
    has_condensation: bool
    condensed_count: int | None
    loadable_events: list[Event]
    loaded_start_index: int


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
        self._replayed_event_offset = 0
        self._replay_complete = False

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

    def replay_historical_events(self) -> int:
        """Replay historical events from the conversation into the visualizer.

        Uses a 3-level deterministic cascade:
        1) Condensation-aware summary + tail path
        2) Windowed tail path
        3) Full passthrough path (only when total <= window)

        Returns:
            Count of replayed events, or 0 if already replayed or empty.
        """
        if self._replay_complete:
            logger.debug(
                "replay_historical_events: skip (offset=%d)",
                self._replayed_event_offset,
            )
            return 0

        events = self.conversation.state.events
        total_count = len(events)
        window_size = self.visualizer.cli_settings.replay_window_size

        # LOG-1: Entry
        logger.debug(
            "replay_historical_events: entry (offset=%d, events=%d, window=%d)",
            self._replayed_event_offset,
            total_count,
            window_size,
        )
        if total_count == 0:
            logger.debug("replay_historical_events: exit — empty history")
            return 0

        t0 = time.monotonic()
        plan = self._build_replay_plan(events, total_count)

        # LOG-2: Path selected
        path = "condensation" if plan.has_condensation else (
            "window" if plan.hidden_count > 0 else "full"
        )
        logger.debug(
            "replay_historical_events: path=%s total=%d tail=%d hidden=%d condensed=%s",
            path, plan.total_count, len(plan.tail_events), plan.hidden_count,
            plan.condensed_count,
        )

        self.visualizer.set_replay_context(
            all_events=plan.loadable_events,
            loaded_start_index=plan.loaded_start_index,
            summary_text=plan.summary_text,
            has_condensation=plan.has_condensation,
            condensed_count=plan.condensed_count,
        )

        if plan.hidden_count > 0:
            self.visualizer.replay_with_summary(
                summary_text=plan.summary_text,
                tail_events=plan.tail_events,
                total_count=plan.total_count,
                hidden_count=plan.hidden_count,
                has_condensation=plan.has_condensation,
                condensed_count=plan.condensed_count,
            )
        else:
            self.visualizer.replay_events(plan.tail_events)

        self._replayed_event_offset = len(plan.tail_events)
        self._replay_complete = True
        elapsed_ms = (time.monotonic() - t0) * 1000

        # LOG-3: Exit with metrics
        logger.debug(
            "replay_historical_events: exit — replayed=%d widgets, duration=%.1fms",
            self._replayed_event_offset, elapsed_ms,
        )
        return self._replayed_event_offset

    def _build_replay_plan(
        self, events: Sequence[Event] | Iterable[Event], total_count: int
    ) -> ReplayPlan:
        """Build deterministic replay plan with condensation→window→full cascade."""
        window_size = self.visualizer.cli_settings.replay_window_size

        try:
            condensation_plan = self._build_condensation_plan(events, total_count)
            if condensation_plan is not None:
                # LOG-4: Condensation path selected
                logger.debug(
                    "_build_replay_plan: condensation path — summary=%s, forgotten=%s",
                    condensation_plan.summary_text is not None,
                    condensation_plan.condensed_count,
                )
                return condensation_plan
        except Exception as exc:
            # LOG-5: Fallback triggered
            logger.warning(
                "_build_replay_plan: condensation failed, fallback to window/full: %s",
                exc,
            )

        tail_events = self._extract_tail_events(events, min(window_size, total_count))
        hidden_count = max(0, total_count - len(tail_events))
        return ReplayPlan(
            summary_text=None,
            tail_events=tail_events,
            total_count=total_count,
            hidden_count=hidden_count,
            has_condensation=False,
            condensed_count=None,
            loadable_events=list(events) if isinstance(events, Sequence) else tail_events,
            loaded_start_index=max(0, total_count - len(tail_events)),
        )

    def _build_condensation_plan(
        self, events: Sequence[Event] | Iterable[Event], total_count: int
    ) -> ReplayPlan | None:
        """Build summary+tail replay plan from latest Condensation event."""
        latest: Condensation | None = None
        tail_source: list[Event] = []

        if isinstance(events, Sequence):
            sequence_events = list(events)
            latest_idx = -1
            for idx in range(len(sequence_events) - 1, -1, -1):
                candidate = sequence_events[idx]
                if isinstance(candidate, Condensation):
                    latest = candidate
                    latest_idx = idx
                    break

            if latest is None:
                return None

            tail_source = list(sequence_events[latest_idx + 1 :])
        else:
            for event in events:
                if isinstance(event, Condensation):
                    latest = event
                    tail_source = []
                    continue
                tail_source.append(event)

            if latest is None:
                return None

        forgotten = set(latest.forgotten_event_ids)
        tail_events = [
            event
            for event in tail_source
            if event.id not in forgotten and not isinstance(event, Condensation)
        ]

        hidden_count = max(0, total_count - len(tail_events))
        loadable_events = tail_source
        loaded_start_index = max(0, len(loadable_events) - len(tail_events))

        return ReplayPlan(
            summary_text=latest.summary,
            tail_events=tail_events,
            total_count=total_count,
            hidden_count=hidden_count,
            has_condensation=True,
            condensed_count=len(forgotten),
            loadable_events=loadable_events,
            loaded_start_index=loaded_start_index,
        )

    def _extract_tail_events(
        self, events: Sequence[Event] | Iterable[Event], window_size: int
    ) -> list[Event]:
        """Extract latest window with slice-preferred/deque-fallback strategy."""
        if window_size <= 0:
            return []

        if isinstance(events, Sequence):
            return list(events[-window_size:])

        return list(deque(events, maxlen=window_size))

    def load_older_events(self) -> int:
        """Load an older replay page through the visualizer."""
        return self.visualizer.load_older_events()

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
