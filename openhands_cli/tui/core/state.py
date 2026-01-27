"""Centralized state management for OpenHands TUI.

This module provides AppState, a centralized state container that:
- Holds all reactive state properties for the TUI
- Owns the ConversationRunner (lazy initialization)
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
    from openhands_cli.tui.core.conversation_runner import ConversationRunner

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
        *,
        env_overrides_enabled: bool = False,
        critic_disabled: bool = False,
        json_mode: bool = False,
        **kwargs,
    ) -> None:
        # Initialize internal state BEFORE calling super().__init__
        # because reactive watchers may be triggered during initialization
        self._conversation_start_time: float | None = None
        self._conversation: BaseConversation | None = None
        self._timer = None
        self._main_thread_id = threading.current_thread().ident

        # ConversationRunner - lazy initialized on first use
        self._conversation_runner: ConversationRunner | None = None

        # Runner configuration (stored for lazy init)
        self._env_overrides_enabled = env_overrides_enabled
        self._critic_disabled = critic_disabled
        self._json_mode = json_mode

        # AppState is a Container that wraps MainDisplay
        # This allows all child widgets to use data_bind() with AppState properties
        super().__init__(id="app_state", **kwargs)

        if initial_confirmation_policy is not None:
            self.confirmation_policy = initial_confirmation_policy

    def compose(self):
        """Compose MainDisplay and input area widgets.

        AppState composes all widgets that need to bind to its reactive properties.
        This is required because data_bind() checks that the active message pump
        (the compose caller) is an instance of the reactive owner class.

        By yielding widgets here, data_bind(AppState.xxx) works because
        the active message pump during compose is AppState itself.
        """
        from textual.widgets import Static

        from openhands_cli.tui.widgets.input_area import InputAreaContainer
        from openhands_cli.tui.widgets.main_display import MainDisplay
        from openhands_cli.tui.widgets.splash import SplashConversation
        from openhands_cli.tui.widgets.status_line import (
            InfoStatusLine,
            WorkingStatusLine,
        )
        from openhands_cli.tui.widgets.user_input.input_field import InputField

        # MainDisplay handles UserInputSubmitted to render user messages
        with MainDisplay(id="main_display"):
            # Splash content widgets
            yield Static(id="splash_banner", classes="splash-banner")
            yield Static(id="splash_version", classes="splash-version")
            yield Static(id="splash_status", classes="status-panel")
            # SplashConversation auto-updates via data_bind
            yield SplashConversation(id="splash_conversation").data_bind(
                conversation_id=AppState.conversation_id
            )
            yield Static(
                id="splash_instructions_header",
                classes="splash-instruction-header",
            )
            yield Static(id="splash_instructions", classes="splash-instruction")
            yield Static(id="splash_update_notice", classes="splash-update-notice")
            yield Static(id="splash_critic_notice", classes="splash-critic-notice")

            # Input area docked to bottom of MainDisplay viewport
            with InputAreaContainer(id="input_area"):
                # Status lines and input field with data_bind
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
        _old_value: ConfirmationPolicyBase,
        _new_value: ConfirmationPolicyBase,
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

        Resets: running, elapsed_seconds, metrics, conversation_title,
                conversation_runner, internal state.
        Preserves: confirmation_policy (persists across conversations),
                   conversation_id (set explicitly when switching).
        """
        self.running = False
        self.elapsed_seconds = 0
        self.metrics = None
        self.conversation_title = None
        self._conversation_start_time = None
        self._conversation = None
        self._conversation_runner = None

    # ---- ConversationRunner Management ----

    @property
    def conversation_runner(self) -> "ConversationRunner | None":
        """Get the conversation runner (may be None if not yet initialized)."""
        return self._conversation_runner

    @conversation_runner.setter
    def conversation_runner(self, value: "ConversationRunner | None") -> None:
        """Set the conversation runner."""
        self._conversation_runner = value

    def get_or_create_runner(self) -> "ConversationRunner":
        """Get existing runner or create a new one (lazy initialization).

        This is the preferred way to get the runner when you need to ensure
        one exists. Uses self.app to access App-level resources.

        Returns:
            The ConversationRunner instance.
        """
        if self._conversation_runner is None:
            self._conversation_runner = self._create_conversation_runner()
        return self._conversation_runner

    def _create_conversation_runner(self) -> "ConversationRunner":
        """Create a new ConversationRunner.

        Uses self.app to access:
        - main_display for visualizer
        - notify() for notifications
        - _handle_confirmation_request for confirmations
        """
        from openhands_cli.tui.core.conversation_runner import ConversationRunner

        # Import for type checking
        from openhands_cli.tui.textual_app import OpenHandsApp
        from openhands_cli.tui.widgets.main_display import MainDisplay
        from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer
        from openhands_cli.utils import json_callback

        # Get app reference - available since AppState is a mounted widget
        app: OpenHandsApp = self.app  # type: ignore[assignment]

        # Get main_display from app
        main_display = app.query_one("#main_display", MainDisplay)

        # Create visualizer that renders to main_display
        conversation_visualizer = ConversationVisualizer(
            main_display, app, skip_user_messages=True, name="OpenHands Agent"
        )

        # Create JSON callback if in JSON mode
        event_callback = json_callback if self._json_mode else None

        # conversation_id is always set before this is called
        assert self.conversation_id is not None

        # Create runner with callbacks that use self.app
        runner = ConversationRunner(
            self.conversation_id,
            app_state=self,
            confirmation_callback=app._handle_confirmation_request,
            notification_callback=lambda title, message, severity: (
                app.notify(title=title, message=message, severity=severity)
            ),
            visualizer=conversation_visualizer,
            event_callback=event_callback,
            env_overrides_enabled=self._env_overrides_enabled,
            critic_disabled=self._critic_disabled,
        )

        return runner
