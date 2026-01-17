"""Centralized state management for OpenHands TUI.

This module provides a message-based state management system. The StateManager
holds all conversation state and emits Textual messages when state changes.
UI widgets listen for these messages and update accordingly.

Usage:
    # In app:
    state_manager = StateManager()
    
    # Widgets listen for state changes via message handlers:
    @on(StateChanged)
    def _on_state_changed(self, event: StateChanged) -> None:
        if event.key == "is_running":
            self._update_display()
    
    # Update state (triggers message emission):
    state_manager.set_running(True)
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from textual.message import Message
from textual.reactive import var
from textual.widget import Widget

if TYPE_CHECKING:
    from openhands.sdk.event import ActionEvent


@dataclass
class ConversationMetrics:
    """Metrics for the current conversation."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hit_rate: str = "N/A"
    last_request_input_tokens: int = 0
    context_window: int = 0
    accumulated_cost: float = 0.0


@dataclass
class ConversationStateSnapshot:
    """Immutable snapshot of conversation state.
    
    This dataclass holds the complete state of a conversation at a point in time.
    Used for state transitions and history tracking.
    """
    is_running: bool = False
    is_confirmation_mode: bool = True
    cloud_ready: bool = True
    cloud_mode: bool = False
    elapsed_seconds: int = 0
    pending_actions_count: int = 0
    metrics: ConversationMetrics = field(default_factory=ConversationMetrics)


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


class StateManager(Widget):
    """Centralized state manager for conversation UI.
    
    This widget holds all conversation state and emits Textual messages when
    state changes. UI widgets listen for these messages to update their display.
    
    Example:
        # In widget:
        @on(StateChanged)
        def _on_state_changed(self, event: StateChanged) -> None:
            if event.key == "is_running":
                self._update_display()
        
        @on(ConversationStarted)
        def _on_conversation_started(self, event: ConversationStarted) -> None:
            self._show_running_indicator()
        
        # State updates trigger message emission:
        state_manager.set_running(True)  # Emits ConversationStarted message
    """
    
    # ---- Core Running State ----
    is_running: var[bool] = var(False)
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
    input_tokens: var[int] = var(0)
    output_tokens: var[int] = var(0)
    cache_hit_rate: var[str] = var("N/A")
    last_request_input_tokens: var[int] = var(0)
    context_window: var[int] = var(0)
    accumulated_cost: var[float] = var(0.0)
    
    # ---- UI State ----
    is_multiline_mode: var[bool] = var(False)
    """Whether input field is in multiline mode."""
    
    # Internal state
    _conversation_start_time: float | None = None
    _timer = None
    
    def __init__(self, cloud_mode: bool = False, **kwargs) -> None:
        # Don't render this widget - it's just a state container
        super().__init__(**kwargs)
        self.display = False
        self.set_reactive(StateManager.cloud_mode, cloud_mode)
        self.set_reactive(StateManager.cloud_ready, not cloud_mode)
    
    def on_mount(self) -> None:
        """Start the elapsed time timer."""
        self._timer = self.set_interval(1.0, self._update_elapsed)
    
    def on_unmount(self) -> None:
        """Clean up timer."""
        if self._timer:
            self._timer.stop()
            self._timer = None
    
    def _update_elapsed(self) -> None:
        """Update elapsed seconds while running."""
        if self.is_running and self._conversation_start_time is not None:
            import time
            new_elapsed = int(time.time() - self._conversation_start_time)
            if new_elapsed != self.elapsed_seconds:
                old_elapsed = self.elapsed_seconds
                self.elapsed_seconds = new_elapsed
                self.post_message(StateChanged("elapsed_seconds", old_elapsed, new_elapsed))
    
    # ---- State Change Watchers ----
    
    def watch_is_running(self, old_value: bool, new_value: bool) -> None:
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
        self.post_message(StateChanged("is_running", old_value, new_value))
    
    def watch_cloud_ready(self, old_value: bool, new_value: bool) -> None:
        """Handle cloud ready state transitions."""
        if new_value and not old_value:
            self.post_message(StateChanged("cloud_ready", old_value, new_value))
    
    # ---- State Update Methods ----
    
    def set_running(self, is_running: bool) -> None:
        """Set the running state."""
        self.is_running = is_running
    
    def set_confirmation_mode(self, is_active: bool) -> None:
        """Set confirmation mode state."""
        self.is_confirmation_mode = is_active
    
    def set_cloud_ready(self, ready: bool = True) -> None:
        """Set cloud workspace ready state."""
        self.cloud_ready = ready
    
    def set_pending_actions(self, count: int) -> None:
        """Set the number of pending actions."""
        self.pending_actions_count = count
    
    def update_metrics(
        self,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cache_hit_rate: str | None = None,
        last_request_input_tokens: int | None = None,
        context_window: int | None = None,
        accumulated_cost: float | None = None,
    ) -> None:
        """Update conversation metrics.
        
        Only updates provided values, leaving others unchanged.
        """
        if input_tokens is not None:
            self.input_tokens = input_tokens
        if output_tokens is not None:
            self.output_tokens = output_tokens
        if cache_hit_rate is not None:
            self.cache_hit_rate = cache_hit_rate
        if last_request_input_tokens is not None:
            self.last_request_input_tokens = last_request_input_tokens
        if context_window is not None:
            self.context_window = context_window
        if accumulated_cost is not None:
            self.accumulated_cost = accumulated_cost
    
    def get_snapshot(self) -> ConversationStateSnapshot:
        """Get an immutable snapshot of current state."""
        return ConversationStateSnapshot(
            is_running=self.is_running,
            is_confirmation_mode=self.is_confirmation_mode,
            cloud_ready=self.cloud_ready,
            cloud_mode=self.cloud_mode,
            elapsed_seconds=self.elapsed_seconds,
            pending_actions_count=self.pending_actions_count,
            metrics=ConversationMetrics(
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                cache_hit_rate=self.cache_hit_rate,
                last_request_input_tokens=self.last_request_input_tokens,
                context_window=self.context_window,
                accumulated_cost=self.accumulated_cost,
            )
        )
    
    def reset(self) -> None:
        """Reset state for a new conversation."""
        self.is_running = False
        self.elapsed_seconds = 0
        self.pending_actions_count = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_hit_rate = "N/A"
        self.last_request_input_tokens = 0
        self.context_window = 0
        self.accumulated_cost = 0.0
        self._conversation_start_time = None
