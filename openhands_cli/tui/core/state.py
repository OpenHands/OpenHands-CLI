"""Centralized state management for OpenHands TUI."""

from typing import TYPE_CHECKING, Any

from textual.containers import Container
from textual.message import Message
from textual.reactive import var

from openhands.sdk.llm.utils.metrics import Metrics


if TYPE_CHECKING:
    from openhands.sdk.event import ActionEvent


class StateChanged(Message):
    """Message emitted when conversation state changes.

    Widgets can listen to this message for complex state change reactions
    that can't be handled by simple reactive bindings.
    """

    def __init__(self, key: str, old_value: Any, new_value: Any) -> None:
        super().__init__()
        self.key = key
        self.old_value = old_value
        self.new_value = new_value


class ConversationFinished(Message):
    """Message emitted when conversation finishes running."""

    pass


class ConversationStarted(Message):
    """Message emitted when conversation starts running."""

    pass


class ConfirmationRequired(Message):
    """Message emitted when actions require user confirmation."""

    def __init__(self, pending_actions: list["ActionEvent"]) -> None:
        super().__init__()
        self.pending_actions = pending_actions


class StateManager(Container):
    """Centralized state manager and container for conversation UI.

    This widget serves as a parent container for UI components that need
    reactive state. Child widgets can use data_bind() to bind to StateManager's
    reactive properties, which automatically updates them when state changes.

    Example:
        # In compose(), yield widgets as children of StateManager:
        with state_manager:
            yield WorkingStatusLine().data_bind(
                running=StateManager.running,
                elapsed_seconds=StateManager.elapsed_seconds,
            )

        # State updates automatically propagate to bound children:
        state_manager.set_running(True)  # WorkingStatusLine updates automatically

    The StateManager also emits messages for complex state transitions.
    """

    # ---- Core Running State ----
    # Note: Named 'running' to avoid conflict with MessagePump.is_running property
    running: var[bool] = var(False)
    """Whether the conversation is currently running/processing."""

    # ---- Confirmation Mode ----
    is_confirmation_mode: var[bool] = var(True)
    """Whether confirmation mode is active (user must approve actions)."""

    pending_actions_count: var[int] = var(0)
    """Number of actions pending user confirmation."""

    # ---- Cloud State ----
    cloud_mode: var[bool] = var(False)
    """Whether running in cloud mode."""

    cloud_ready: var[bool] = var(True)
    """Whether cloud workspace is ready (always True if not cloud mode)."""

    # ---- Timing ----
    elapsed_seconds: var[int] = var(0)
    """Seconds elapsed since conversation started."""

    # ---- Metrics ----
    # Store the Metrics object directly from conversation stats
    metrics: var[Metrics | None] = var(None)
    """Combined metrics from conversation stats (updated by ConversationRunner)."""

    # ---- UI State ----
    is_multiline_mode: var[bool] = var(False)
    """Whether input field is in multiline mode."""

    # Internal state
    _conversation_start_time: float | None = None
    _timer = None

    def __init__(self, cloud_mode: bool = False, **kwargs) -> None:
        # Set id to "input_area" so CSS styling applies correctly
        super().__init__(id="input_area", **kwargs)
        self.set_reactive(StateManager.cloud_mode, cloud_mode)
        self.set_reactive(StateManager.cloud_ready, not cloud_mode)

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
        """Update elapsed seconds while running."""
        if self.running and self._conversation_start_time is not None:
            import time

            new_elapsed = int(time.time() - self._conversation_start_time)
            if new_elapsed != self.elapsed_seconds:
                old_elapsed = self.elapsed_seconds
                self.elapsed_seconds = new_elapsed
                self.post_message(
                    StateChanged("elapsed_seconds", old_elapsed, new_elapsed)
                )

    # ---- State Change Watchers ----

    def watch_running(self, old_value: bool, new_value: bool) -> None:
        """Handle running state transitions."""
        import time

        if new_value and not old_value:
            # Started running
            self._conversation_start_time = time.time()
            self.elapsed_seconds = 0
            self.post_message(ConversationStarted())
        elif not new_value and old_value:
            # Stopped running
            self._conversation_start_time = None
            self.post_message(ConversationFinished())

        # Emit generic state changed message
        self.post_message(StateChanged("running", old_value, new_value))

    def watch_cloud_ready(self, old_value: bool, new_value: bool) -> None:
        """Handle cloud ready state transitions."""
        if new_value and not old_value:
            self.post_message(StateChanged("cloud_ready", old_value, new_value))

    # ---- State Update Methods ----
    # These methods are thread-safe and can be called from background threads.

    def set_running(self, value: bool) -> None:
        """Set the running state. Thread-safe."""
        self._schedule_update("running", value)

    def set_confirmation_mode(self, is_active: bool) -> None:
        """Set confirmation mode state. Thread-safe."""
        self._schedule_update("is_confirmation_mode", is_active)

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

    def set_cloud_ready(self, ready: bool = True) -> None:
        """Set cloud workspace ready state. Thread-safe."""
        self._schedule_update("cloud_ready", ready)

    def set_pending_actions(self, count: int) -> None:
        """Set the number of pending actions. Thread-safe."""
        self._schedule_update("pending_actions_count", count)

    def set_metrics(self, metrics: Metrics) -> None:
        """Set the metrics object. Thread-safe.

        Called by ConversationRunner to update metrics from conversation stats.
        """
        self._schedule_update("metrics", metrics)

    def reset(self) -> None:
        """Reset state for a new conversation."""
        self.running = False
        self.elapsed_seconds = 0
        self.pending_actions_count = 0
        self.metrics = None
        self._conversation_start_time = None
