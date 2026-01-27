"""Centralized state management for OpenHands TUI."""

import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from textual.containers import Container
from textual.message import Message
from textual.reactive import var

from openhands.sdk.llm.utils.metrics import Metrics
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmationPolicyBase,
    NeverConfirm,
)


if TYPE_CHECKING:
    from openhands.sdk import BaseConversation
    from openhands.sdk.event import ActionEvent

logger = logging.getLogger(__name__)


class ConversationFinished(Message):
    """Message emitted when conversation finishes running."""

    pass


class StateManager(Container):
    """Centralized state manager and container for conversation UI.

    This widget serves as a parent container for UI components that need
    reactive state. Child widgets can use data_bind() to bind to StateManager's
    reactive properties, which automatically updates them when state changes.

    For dynamically mounted widgets (like HistorySidePanel), use self.watch()
    to subscribe to StateManager's reactive properties.

    StateManager OWNS:
    - Confirmation policy (synced to attached conversation)
    - Conversation identity (conversation_id, conversation_title)
    - Running state and metrics

    Example:
        # Child widgets use data_bind():
        with state_manager:
            yield WorkingStatusLine().data_bind(
                running=StateManager.running,
                elapsed_seconds=StateManager.elapsed_seconds,
            )

        # Dynamically mounted widgets use self.watch():
        class HistorySidePanel(Container):
            def on_mount(self):
                self.watch(self.app.state_manager, "conversation_id", self._on_change)

        # State updates automatically propagate:
        state_manager.set_running(True)
        state_manager.set_conversation_id(new_id)

    The StateManager also emits messages for complex state transitions.
    """

    # ---- Core Running State ----
    running: var[bool] = var(False)
    """Whether the conversation is currently running/processing."""

    # ---- Conversation Identity ----
    conversation_id: var[uuid.UUID | None] = var(None)
    """The currently active conversation ID."""

    conversation_title: var[str | None] = var(None)
    """The title of the current conversation (first user message)."""

    is_switching: var[bool] = var(False)
    """Whether a conversation switch is in progress."""

    # ---- Confirmation Policy (StateManager owns this) ----
    confirmation_policy: var[ConfirmationPolicyBase] = var(AlwaysConfirm())
    """The confirmation policy. StateManager owns this and syncs to conversation."""

    # ---- Timing ----
    elapsed_seconds: var[int] = var(0)
    """Seconds elapsed since conversation started."""

    # ---- Metrics ----
    metrics: var[Metrics | None] = var(None)
    """Combined metrics from conversation stats."""

    # ---- UI State ----
    is_multiline_mode: var[bool] = var(False)
    """Whether input field is in multiline mode."""

    # Internal state
    _conversation_start_time: float | None = None
    _timer = None
    _conversation: "BaseConversation | None" = None

    def __init__(
        self,
        initial_confirmation_policy: ConfirmationPolicyBase | None = None,
        **kwargs,
    ) -> None:
        # Set id to "input_area" so CSS styling applies correctly
        super().__init__(id="input_area", **kwargs)
        if initial_confirmation_policy is not None:
            self.confirmation_policy = initial_confirmation_policy

    @property
    def is_confirmation_active(self) -> bool:
        """Check if confirmation is required (not NeverConfirm)."""
        return not isinstance(self.confirmation_policy, NeverConfirm)

    def on_mount(self) -> None:
        """Start the elapsed time timer."""
        self._timer = self.set_interval(1.0, self._update_elapsed)

    def compose(self):
        # Import here to avoid circular imports
        from openhands_cli.tui.widgets.status_line import (
            InfoStatusLine,
            WorkingStatusLine,
        )
        from openhands_cli.tui.widgets.user_input.input_field import InputField

        yield WorkingStatusLine().data_bind(
            running=StateManager.running,
            elapsed_seconds=StateManager.elapsed_seconds,
        )
        yield InputField(
            placeholder="Type your message, @mention a file, or / for commands"
        )
        # InfoStatusLine binds to StateManager reactive properties
        # metrics is the Metrics object from conversation stats
        yield InfoStatusLine().data_bind(
            running=StateManager.running,
            is_multiline_mode=StateManager.is_multiline_mode,
            metrics=StateManager.metrics,
        )

    def on_unmount(self) -> None:
        """Clean up timer."""
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _update_elapsed(self) -> None:
        """Update elapsed seconds and metrics while running."""

        if not self.running:
            return

        if not self._conversation_start_time:
            return

        new_elapsed = int(time.time() - self._conversation_start_time)
        if new_elapsed != self.elapsed_seconds:
            self.elapsed_seconds = new_elapsed

        # Update metrics from conversation stats
        self._update_metrics()

    # ---- State Change Watchers ----

    def watch_running(self, old_value: bool, new_value: bool) -> None:
        """Handle running state transitions."""
        import time

        if new_value and not old_value:
            # Started running
            self._conversation_start_time = time.time()
            self.elapsed_seconds = 0
        elif not new_value and old_value:
            # Stopped running
            self._conversation_start_time = None
            self.post_message(ConversationFinished())

    # ---- State Update Methods ----
    # These methods are thread-safe and can be called from background threads.

    def set_running(self, value: bool) -> None:
        """Set the running state. Thread-safe."""
        self._schedule_update("running", value)

    def set_confirmation_policy(self, policy: ConfirmationPolicyBase) -> None:
        """Set the confirmation policy. Thread-safe.

        This is the single entry point for all confirmation policy changes.
        The policy is automatically synced to the attached conversation.

        Args:
            policy: The new confirmation policy to set.
        """
        self._schedule_update("confirmation_policy", policy)

    def watch_confirmation_policy(
        self,
        old_value: ConfirmationPolicyBase,
        new_value: ConfirmationPolicyBase,
    ) -> None:
        """React to confirmation policy changes - sync to attached conversation."""
        self._sync_policy_to_conversation()

    def attach_conversation(self, conversation: "BaseConversation") -> None:
        """Attach a conversation and sync the current policy to it.

        Args:
            conversation: The conversation to attach.
        """
        self._conversation = conversation
        self._sync_policy_to_conversation()

    def _sync_policy_to_conversation(self) -> None:
        """Sync the current confirmation policy to the attached conversation.

        Note: The security analyzer is set once during conversation creation
        (in setup.py). This method only syncs the confirmation policy.
        """
        if self._conversation is None:
            return

        try:
            self._conversation.set_confirmation_policy(self.confirmation_policy)
            logger.debug(
                f"Synced confirmation policy: {type(self.confirmation_policy).__name__}"
            )
        except Exception as e:
            logger.error(f"Failed to sync confirmation policy: {e}")

    def _schedule_update(self, attr: str, value: Any) -> None:
        """Schedule a state update, handling cross-thread calls.

        When called from a background thread, uses call_from_thread to
        schedule the update on the main thread.
        """

        def do_update() -> None:
            setattr(self, attr, value)

        # Check if we're in the main thread by checking for active app
        try:
            # If we can get the app, we're in the right context
            _ = self.app
            do_update()
        except Exception:
            # We're in a background thread, need to schedule on main thread
            # Use app.call_from_thread which is thread-safe
            self.app.call_from_thread(do_update)

    def set_metrics(self, metrics: Metrics) -> None:
        """Set the metrics object. Thread-safe."""
        self._schedule_update("metrics", metrics)

    def _update_metrics(self) -> None:
        """Update metrics from conversation stats."""
        if self._conversation is None:
            return

        stats = self._conversation.state.stats
        if stats:
            combined_metrics = stats.get_combined_metrics()
            self.metrics = combined_metrics

    # ---- Conversation Identity Methods ----

    def set_conversation_id(self, conversation_id: uuid.UUID) -> None:
        """Set the current conversation ID. Thread-safe."""
        self._schedule_update("conversation_id", conversation_id)

    def set_conversation_title(self, title: str) -> None:
        """Set the conversation title. Thread-safe."""
        self._schedule_update("conversation_title", title)

    def start_switching(self) -> None:
        """Mark that a conversation switch is in progress. Thread-safe."""
        self._schedule_update("is_switching", True)

    def finish_switching(self) -> None:
        """Mark that a conversation switch has completed. Thread-safe."""
        self._schedule_update("is_switching", False)

    def reset(self) -> None:
        """Reset state for a new conversation."""
        self.running = False
        self.elapsed_seconds = 0
        self.metrics = None
        self.conversation_title = None
        self._conversation_start_time = None
        self._conversation = None
        # Note: confirmation_policy is NOT reset - it persists across conversations
        # Note: conversation_id is NOT reset here - set explicitly when switching
