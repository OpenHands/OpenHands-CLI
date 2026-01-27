"""Centralized state management for OpenHands TUI.

This module provides AppState, a centralized state container that:
- Holds all reactive state properties for the TUI
- Composes the input area widgets (required for Textual's data_bind)
- Provides thread-safe state update methods

The design follows Textual's reactive pattern where widgets bind to
ancestor state via data_bind() for automatic UI updates.
"""

import logging
import threading
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


class ConfirmationRequired(Message):
    """Message emitted when actions require user confirmation."""

    def __init__(self, pending_actions: list["ActionEvent"]) -> None:
        super().__init__()
        self.pending_actions = pending_actions


class AppState(Container):
    """Centralized state container for the TUI with reactive properties.

    AppState is responsible for:
    - Managing all reactive state (running, conversation_id, metrics, etc.)
    - Composing the input area widgets (required for data_bind to work)
    - Providing thread-safe state update methods
    - Syncing confirmation policy to attached conversations

    Widgets can bind to AppState's reactive properties using data_bind()
    or watch() for automatic updates when state changes.

    Example:
        # In OpenHandsApp:
        self.app_state = AppState(initial_confirmation_policy=AlwaysConfirm())

        # Child widgets bind to state via data_bind():
        WorkingStatusLine().data_bind(
            running=AppState.running,
            elapsed_seconds=AppState.elapsed_seconds,
        )

        # Dynamically mounted widgets use watch():
        self.watch(app.app_state, "conversation_id", self._on_change)

        # State updates propagate automatically:
        app_state.set_running(True)
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

    # ---- Confirmation Policy ----
    confirmation_policy: var[ConfirmationPolicyBase] = var(AlwaysConfirm())
    """The confirmation policy. AppState owns this and syncs to conversation."""

    # ---- Timing ----
    elapsed_seconds: var[int] = var(0)
    """Seconds elapsed since conversation started."""

    # ---- Metrics ----
    metrics: var[Metrics | None] = var(None)
    """Combined metrics from conversation stats."""

    # ---- UI State ----
    is_multiline_mode: var[bool] = var(False)
    """Whether input field is in multiline mode."""

    def __init__(
        self,
        initial_confirmation_policy: ConfirmationPolicyBase | None = None,
        **kwargs,
    ) -> None:
        # Initialize internal state BEFORE calling super().__init__
        # because reactive watchers may be triggered during initialization
        self._conversation_start_time: float | None = None
        self._conversation: "BaseConversation | None" = None
        self._timer = None
        self._main_thread_id = threading.current_thread().ident

        # AppState is a Container that holds state and composes InputAreaContainer
        # The id="input_area" is for CSS styling compatibility
        super().__init__(id="input_area", **kwargs)

        if initial_confirmation_policy is not None:
            self.confirmation_policy = initial_confirmation_policy

    def compose(self):
        """Compose the input area with status lines and input field.

        While AppState is primarily a state holder, it also composes the input
        area widgets. This is necessary because Textual's data_bind() requires
        the reactive source to be an ancestor of the bound widget.
        """
        # Import here to avoid circular imports
        from openhands_cli.tui.widgets.status_line import (
            InfoStatusLine,
            WorkingStatusLine,
        )
        from openhands_cli.tui.widgets.user_input.input_field import InputField

        # Bind child widgets to AppState's reactive properties
        yield WorkingStatusLine().data_bind(
            running=AppState.running,
            elapsed_seconds=AppState.elapsed_seconds,
        )
        yield InputField(
            placeholder="Type your message, @mention a file, or / for commands"
        )
        yield InfoStatusLine().data_bind(
            running=AppState.running,
            is_multiline_mode=AppState.is_multiline_mode,
            metrics=AppState.metrics,
        )

    @property
    def is_confirmation_active(self) -> bool:
        """Check if confirmation is required (not NeverConfirm)."""
        return not isinstance(self.confirmation_policy, NeverConfirm)

    def on_mount(self) -> None:
        """Start the elapsed time timer."""
        self._main_thread_id = threading.current_thread().ident
        self._timer = self.set_interval(1.0, self._update_elapsed)

    def on_unmount(self) -> None:
        """Clean up timer."""
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _update_elapsed(self) -> None:
        """Update elapsed seconds and metrics while running."""
        if not self.running or not self._conversation_start_time:
            return

        new_elapsed = int(time.time() - self._conversation_start_time)
        if new_elapsed != self.elapsed_seconds:
            self.elapsed_seconds = new_elapsed

        # Update metrics from conversation stats
        self._update_metrics()

    # ---- State Change Watchers ----

    def watch_running(self, old_value: bool, new_value: bool) -> None:
        """Handle running state transitions."""
        if new_value and not old_value:
            # Started running
            self._conversation_start_time = time.time()
            self.elapsed_seconds = 0
        elif not new_value and old_value:
            # Stopped running
            self._conversation_start_time = None
            self.post_message(ConversationFinished())

    def watch_confirmation_policy(
        self,
        old_value: ConfirmationPolicyBase,
        new_value: ConfirmationPolicyBase,
    ) -> None:
        """React to confirmation policy changes - sync to attached conversation."""
        self._sync_policy_to_conversation()

    # ---- Thread-Safe State Update Methods ----

    def _is_main_thread(self) -> bool:
        """Check if we're on the main thread."""
        return threading.current_thread().ident == self._main_thread_id

    def _schedule_update(self, attr: str, value: Any) -> None:
        """Schedule a state update, handling cross-thread calls.

        Uses threading.current_thread() for reliable thread detection
        instead of exception-based control flow.
        """

        def do_update() -> None:
            setattr(self, attr, value)

        if self._is_main_thread():
            do_update()
        else:
            # We're in a background thread, schedule on main thread
            self.app.call_from_thread(do_update)

    def set_running(self, value: bool) -> None:
        """Set the running state. Thread-safe."""
        self._schedule_update("running", value)

    def set_confirmation_policy(self, policy: ConfirmationPolicyBase) -> None:
        """Set the confirmation policy. Thread-safe.

        This is the single entry point for all confirmation policy changes.
        The policy is automatically synced to the attached conversation.
        """
        self._schedule_update("confirmation_policy", policy)

    def set_metrics(self, metrics: Metrics) -> None:
        """Set the metrics object. Thread-safe."""
        self._schedule_update("metrics", metrics)

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

    # ---- Conversation Management ----

    def attach_conversation(self, conversation: "BaseConversation") -> None:
        """Attach a conversation and sync the current policy to it."""
        self._conversation = conversation
        self._sync_policy_to_conversation()

    def _sync_policy_to_conversation(self) -> None:
        """Sync the current confirmation policy to the attached conversation."""
        if self._conversation is None:
            return

        try:
            self._conversation.set_confirmation_policy(self.confirmation_policy)
            logger.debug(
                f"Synced confirmation policy: {type(self.confirmation_policy).__name__}"
            )
        except Exception as e:
            logger.error(f"Failed to sync confirmation policy: {e}")

    def _update_metrics(self) -> None:
        """Update metrics from conversation stats."""
        if self._conversation is None:
            return

        stats = self._conversation.state.stats
        if stats:
            combined_metrics = stats.get_combined_metrics()
            self.metrics = combined_metrics

    def reset_conversation_state(self) -> None:
        """Reset state for a new conversation.

        Resets: running, elapsed_seconds, metrics, conversation_title, internal state.
        Preserves: confirmation_policy (persists across conversations),
                   conversation_id (set explicitly when switching).
        """
        self.running = False
        self.elapsed_seconds = 0
        self.metrics = None
        self.conversation_title = None
        self._conversation_start_time = None
        self._conversation = None


# Backwards compatibility alias
StateManager = AppState
