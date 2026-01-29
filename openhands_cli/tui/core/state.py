"""Centralized state management for OpenHands TUI.

This module provides ConversationView, a centralized state container that:
- Holds all reactive state properties for the TUI
- Owns the ConversationRunner (lazy initialization)
- Composes the scroll view and input area widgets
- Provides thread-safe state update methods

The design follows Textual's reactive pattern where widgets bind to
ancestor state via data_bind() for automatic UI updates.

Widget Hierarchy:
    ConversationView(Container, #conversation_view)
    ├── ScrollableContent(VerticalScroll, #scroll_view)
    │   ├── SplashContent(#splash_content)
    │   └── ... dynamically added conversation widgets
    └── InputAreaContainer(#input_area)  ← docked to bottom
        ├── WorkingStatusLine
        ├── InputField
        └── InfoStatusLine

Message Flow:
    InputField → ConversationView
    - UserInputSubmitted: ConversationView renders and processes with runner
    - SlashCommandSubmitted: InputAreaContainer executes commands
    - NewConversationRequested: ConversationView handles /new command
"""

import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from textual import on
from textual.containers import Container
from textual.message import Message
from textual.reactive import var

from openhands.sdk.llm.utils.metrics import Metrics
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmationPolicyBase,
    NeverConfirm,
)
from openhands_cli.tui.messages import NewConversationRequested, UserInputSubmitted


if TYPE_CHECKING:
    from openhands.sdk import BaseConversation
    from openhands.sdk.event import ActionEvent
    from openhands_cli.tui.core.conversation_runner import ConversationRunner
    from openhands_cli.tui.widgets.input_area import InputAreaContainer
    from openhands_cli.tui.widgets.main_display import ScrollableContent

logger = logging.getLogger(__name__)


class ConversationFinished(Message):
    """Message emitted when conversation finishes running."""

    pass


class ConfirmationRequired(Message):
    """Message emitted when actions require user confirmation."""

    def __init__(self, pending_actions: list["ActionEvent"]) -> None:
        super().__init__()
        self.pending_actions = pending_actions


class ConversationView(Container):
    """Centralized state container for the TUI with reactive properties.

    ConversationView is responsible for:
    - Managing all reactive state (running, conversation_id, metrics, etc.)
    - Composing the conversation-related widgets (required for data_bind to work)
    - Providing thread-safe state update methods
    - Syncing confirmation policy to attached conversations

    Widgets can bind to ConversationView's reactive properties using data_bind()
    or watch() for automatic updates when state changes.

    Example:
        # In OpenHandsApp:
        self.conversation_view = ConversationView(
            initial_confirmation_policy=AlwaysConfirm()
        )

        # Child widgets bind to state via data_bind():
        WorkingStatusLine().data_bind(
            running=ConversationView.running,
            elapsed_seconds=ConversationView.elapsed_seconds,
        )

        # Dynamically mounted widgets use watch():
        self.watch(app.conversation_view, "conversation_id", self._on_change)

        # State updates propagate automatically:
        conversation_view.set_running(True)
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
    """The confirmation policy. ConversationView owns this and syncs to conversation."""

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

        # ConversationRunner - lazy initialized on first use
        self._conversation_runner: ConversationRunner | None = None

        # Runner configuration (stored for lazy init)
        self._env_overrides_enabled = env_overrides_enabled
        self._critic_disabled = critic_disabled
        self._json_mode = json_mode

        # ConversationView is a Container that holds scroll_view and input_area
        super().__init__(id="conversation_view", **kwargs)

        if initial_confirmation_policy is not None:
            self.confirmation_policy = initial_confirmation_policy

    def compose(self):
        """Compose scroll view and input area widgets.

        ConversationView composes all widgets that need to bind to its reactive
        properties. This is required because data_bind() checks that the active
        message pump (the compose caller) is an instance of the reactive owner.

        By yielding widgets here, data_bind(ConversationView.xxx) works because
        the active message pump during compose is ConversationView itself.

        Widget Hierarchy::

            ConversationView(#conversation_view)
            ├── ScrollableContent(#scroll_view)
            │   ├── SplashContent(#splash_content)
            │   └── ... dynamically added conversation widgets
            └── InputAreaContainer(#input_area)  ← docked to bottom

        Note: InputAreaContainer is a SIBLING of ScrollableContent, not a child.
        This ensures widgets mounted to scroll_view are laid out correctly.
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
        with ScrollableContent(id="scroll_view"):
            # SplashContent contains all splash widgets
            # - conversation_id is bound reactively for conversation switching
            # - initialize() is called by OpenHandsApp for one-time setup
            yield SplashContent(id="splash_content").data_bind(
                conversation_id=ConversationView.conversation_id,
            )

        # Input area docked to bottom (sibling of scroll_view)
        # - conversation_id is bound to clear scroll_view content on change
        # - Handles UserInputSubmitted and SlashCommandSubmitted
        with InputAreaContainer(id="input_area").data_bind(
            conversation_id=ConversationView.conversation_id,
        ):
            # Status lines and input field with data_bind
            yield WorkingStatusLine().data_bind(
                running=ConversationView.running,
                elapsed_seconds=ConversationView.elapsed_seconds,
            )
            yield InputField(
                placeholder="Type your message, @mention a file, or / for commands"
            )
            yield InfoStatusLine().data_bind(
                running=ConversationView.running,
                is_multiline_mode=ConversationView.is_multiline_mode,
                metrics=ConversationView.metrics,
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
            self._update_metrics()
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
        - scroll_view for visualizer (the scrollable content area)
        - notify() for notifications
        - _handle_confirmation_request for confirmations
        """
        from openhands_cli.tui.core.conversation_runner import ConversationRunner

        # Import for type checking
        from openhands_cli.tui.textual_app import OpenHandsApp
        from openhands_cli.tui.widgets.main_display import ScrollableContent
        from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer
        from openhands_cli.utils import json_callback

        # Get app reference - available since ConversationView is a mounted widget
        app: OpenHandsApp = self.app  # type: ignore[assignment]

        # Get scroll_view - the scrollable content area where widgets are mounted
        scroll_view = app.query_one("#scroll_view", ScrollableContent)

        # Create visualizer that renders to scroll_view
        conversation_visualizer = ConversationVisualizer(
            scroll_view, app, skip_user_messages=True, name="OpenHands Agent"
        )

        # Create JSON callback if in JSON mode
        event_callback = json_callback if self._json_mode else None

        # Create runner with callbacks that use self.app
        runner = ConversationRunner(
            self.conversation_id,
            conversation_view=self,
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

    # ---- Message Handlers ----

    @on(NewConversationRequested)
    def _on_new_conversation_requested(self, event: NewConversationRequested) -> None:
        """Handle request to start a new conversation.

        This is triggered by the /new command.
        ConversationView owns conversation lifecycle, so it:
        1. Checks if a conversation is running
        2. Creates a new conversation ID
        3. Resets state
        4. Sets new conversation_id (watch_conversation_id clears content)
        5. Notifies the user
        """
        event.stop()

        from openhands_cli.conversations.store.local import LocalFileStore
        from openhands_cli.tui.textual_app import OpenHandsApp

        app: OpenHandsApp = self.app  # type: ignore[assignment]

        # Check if a conversation is currently running
        if self.running:
            app.notify(
                title="New Conversation Error",
                message="Cannot start a new conversation while one is running. "
                "Please wait for the current conversation to complete or pause it.",
                severity="error",
            )
            return

        # Create a new conversation via store
        store = LocalFileStore()
        new_id_str = store.create()
        new_id = uuid.UUID(new_id_str)

        # Reset state (this also clears conversation_runner)
        self.reset_conversation_state()

        # Set new conversation ID - triggers:
        # - watch_conversation_id() clears dynamic content
        # - SplashContent.watch_conversation_id() re-renders
        self.conversation_id = new_id

        # Remove any existing confirmation panel
        if app.confirmation_panel:
            app.confirmation_panel.remove()
            app.confirmation_panel = None

        # Notify user
        app.notify(
            title="New Conversation",
            message="Started a new conversation",
            severity="information",
        )

    @on(UserInputSubmitted)
    async def _on_user_input_submitted(self, event: UserInputSubmitted) -> None:
        """Handle user input by rendering it and processing with the runner.

        ConversationView handles both rendering and processing since it owns
        both the scroll view and the ConversationRunner.
        """
        from textual.widgets import Static

        event.stop()

        # Render the user message in the scrollable content area
        user_message_widget = Static(
            f"> {event.content}", classes="user-message", markup=False
        )
        await self.scroll_view.mount(user_message_widget)
        self.scroll_view.scroll_end(animate=False)

        # Process the message
        await self.process_user_input(event.content)

    async def process_user_input(self, content: str) -> None:
        """Process user input with the conversation runner.

        This method can be called:
        - Via UserInputSubmitted message (for typed inputs)
        - Directly by App (for queued inputs from --task/--file)

        Args:
            content: The user's message content
        """
        from openhands_cli.tui.textual_app import OpenHandsApp

        app: OpenHandsApp = self.app  # type: ignore[assignment]

        # Dismiss any pending critic feedback widgets
        self._dismiss_pending_feedback_widgets()

        # Get or create conversation runner (lazy initialization)
        runner = self.get_or_create_runner()

        # Update conversation title (for history panel)
        self.set_conversation_title(content)

        # If already running, queue the message
        if runner.is_running:
            await runner.queue_message(content)
            return

        # Process message asynchronously to keep UI responsive
        app.run_worker(
            runner.process_message_async(content, app.headless_mode),
            name="process_message",
        )

    def _dismiss_pending_feedback_widgets(self) -> None:
        """Remove all pending CriticFeedbackWidget instances from the UI.

        Called when user sends a new message, indicating they chose to
        ignore the feedback prompt.
        """
        from openhands_cli.tui.utils.critic.feedback import CriticFeedbackWidget
        from openhands_cli.tui.widgets.main_display import ScrollableContent

        scroll_view = self.query_one("#scroll_view", ScrollableContent)

        # Find and remove all CriticFeedbackWidget instances
        for widget in scroll_view.query(CriticFeedbackWidget):
            widget.remove()
