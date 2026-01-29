"""Centralized state management for OpenHands TUI.

This module provides:
- ConversationState: Pure reactive state container for UI binding
- ConversationFinished: Message emitted when conversation finishes

Architecture:
    ConversationState holds reactive properties that UI components bind to.
    ConversationManager (in conversation_manager.py) handles operations and
    updates ConversationState. UI components auto-update via data_bind/watch.

    Policy Sync:
        ConversationManager handles policy sync to conversation objects directly.
        ConversationState only holds the reactive confirmation_policy var for UI.

Widget Hierarchy:
    ConversationState(Container, #conversation_state)
    ├── ScrollableContent(VerticalScroll, #scroll_view)
    │   ├── SplashContent(#splash_content)
    │   └── ... dynamically added conversation widgets
    └── InputAreaContainer(#input_area)  ← docked to bottom
        ├── WorkingStatusLine
        ├── InputField
        └── InfoStatusLine
"""

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
    from openhands.sdk.event import ActionEvent
    from openhands_cli.tui.widgets.input_area import InputAreaContainer
    from openhands_cli.tui.widgets.main_display import ScrollableContent


class ConversationFinished(Message):
    """Message emitted when conversation finishes running."""

    pass


class ConfirmationRequired(Message):
    """Message emitted when actions require user confirmation."""

    def __init__(self, pending_actions: list["ActionEvent"]) -> None:
        super().__init__()
        self.pending_actions = pending_actions


class ConversationState(Container):
    """Pure reactive state container for UI binding.

    ConversationState is responsible for:
    - Holding reactive state (running, conversation_id, metrics, etc.)
    - Composing UI widgets (required for data_bind to work)
    - Providing thread-safe state update methods

    Business logic (creating/switching conversations, sending messages, policy
    sync) is handled by ConversationManager. This class only holds state and
    provides reactive bindings for UI components.

    Example:
        # UI components bind via data_bind():
        WorkingStatusLine().data_bind(
            running=ConversationState.running,
            elapsed_seconds=ConversationState.elapsed_seconds,
        )

        # Dynamically mounted widgets use watch():
        self.watch(state, "conversation_id", self._on_change)

        # ConversationManager updates state:
        state.set_running(True)  # Triggers reactive updates
    """

    # ---- Core Running State ----
    running: var[bool] = var(False)
    """Whether the conversation is currently running/processing."""

    # ---- Conversation Identity ----
    conversation_id: var[uuid.UUID] = var(uuid.uuid4)
    """The currently active conversation ID."""

    conversation_title: var[str | None] = var(None)
    """The title of the current conversation (first user message)."""

    is_switching: var[bool] = var(False)
    """Whether a conversation switch is in progress."""

    # ---- Confirmation Policy ----
    confirmation_policy: var[ConfirmationPolicyBase] = var(AlwaysConfirm())
    """The confirmation policy. ConversationManager syncs this to conversation."""

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
        self._timer = None

        super().__init__(id="conversation_state", **kwargs)

        if initial_confirmation_policy is not None:
            self.confirmation_policy = initial_confirmation_policy

    def compose(self):
        """Compose UI widgets that bind to reactive state.

        ConversationState composes all widgets that need to bind to its reactive
        properties. This is required because data_bind() checks that the active
        message pump (the compose caller) is an instance of the reactive owner.

        Widget Hierarchy::

            ConversationState(#conversation_state)
            ├── ScrollableContent(#scroll_view)
            │   ├── SplashContent(#splash_content)
            │   └── ... dynamically added conversation widgets
            └── InputAreaContainer(#input_area)  ← docked to bottom
        """
        from openhands_cli.tui.widgets.input_area import InputAreaContainer
        from openhands_cli.tui.widgets.main_display import ScrollableContent
        from openhands_cli.tui.widgets.splash import SplashContent
        from openhands_cli.tui.widgets.status_line import (
            InfoStatusLine,
            WorkingStatusLine,
        )
        from openhands_cli.tui.widgets.user_input.input_field import InputField

        # ScrollableContent holds splash and dynamically added widgets
        with ScrollableContent(id="scroll_view").data_bind(
            conversation_id=ConversationState.conversation_id,
        ):
            yield SplashContent(id="splash_content").data_bind(
                conversation_id=ConversationState.conversation_id,
            )

        # Input area docked to bottom
        with InputAreaContainer(id="input_area"):
            yield WorkingStatusLine().data_bind(
                running=ConversationState.running,
                elapsed_seconds=ConversationState.elapsed_seconds,
            )
            yield InputField(
                placeholder="Type your message, @mention a file, or / for commands"
            )
            yield InfoStatusLine().data_bind(
                running=ConversationState.running,
                is_multiline_mode=ConversationState.is_multiline_mode,
                metrics=ConversationState.metrics,
            )

    @property
    def is_confirmation_active(self) -> bool:
        """Check if confirmation is required (not NeverConfirm)."""
        return not isinstance(self.confirmation_policy, NeverConfirm)

    @property
    def scroll_view(self) -> "ScrollableContent":
        """Get the scrollable content area."""
        from openhands_cli.tui.widgets.main_display import ScrollableContent

        return self.query_one("#scroll_view", ScrollableContent)

    @property
    def input_area(self) -> "InputAreaContainer":
        """Get the input area container."""
        from openhands_cli.tui.widgets.input_area import InputAreaContainer

        return self.query_one("#input_area", InputAreaContainer)

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
        if not self.running or not self._conversation_start_time:
            return

        new_elapsed = int(time.time() - self._conversation_start_time)
        if new_elapsed != self.elapsed_seconds:
            self.elapsed_seconds = new_elapsed

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

    # ---- Thread-Safe State Update Methods ----

    def _schedule_update(self, attr: str, value: Any) -> None:
        """Schedule a state update, handling cross-thread calls.

        Uses Textual's call_from_thread() for thread safety. If already on
        the main thread, call_from_thread() raises RuntimeError, so we
        catch that and do the update directly.
        """

        def do_update() -> None:
            setattr(self, attr, value)

        try:
            self.app.call_from_thread(do_update)
        except RuntimeError:
            # Already on main thread - do update directly
            do_update()

    def set_running(self, value: bool) -> None:
        """Set the running state. Thread-safe."""
        self._schedule_update("running", value)

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


# Backward compatibility alias - ConversationView is now ConversationState
ConversationView = ConversationState
