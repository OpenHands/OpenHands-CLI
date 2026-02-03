"""ConversationManager - centralized conversation operations handler.

This module provides ConversationManager, which handles all conversation
operations including creating, switching, and sending messages.

Architecture:
    ConversationManager is a Container that wraps the content area. Messages
    from child components (InputField, InputAreaContainer, HistorySidePanel)
    bubble up through the DOM tree and are handled here.

    Reactive UI:
        UI state changes are reactive via ConversationState:
        - conversation_id=None: InputField disables (switching in progress)
        - conversation_id=UUID: InputField enables (normal operation)

    Direct Calls:
        ConversationManager calls app methods directly:
        - self.app.notify() for notifications
        - self.run_worker() for background tasks

    Events (minimal):
        - RequestSwitchConfirmation: App shows modal, returns SwitchConfirmed

Widget Hierarchy:
    OpenHandsApp
    └── ConversationManager (Container)  ← Messages bubble here
        └── Horizontal(#content_area)
            └── ConversationState  ← Owns reactive state
                └── InputAreaContainer, etc.

Message Flow (natural bubbling):
    InputField → UserInputSubmitted → bubbles up → ConversationManager
    InputAreaContainer → CreateConversation → bubbles up → ConversationManager
    HistorySidePanel → SwitchConversation → bubbles up → ConversationManager

State Updates:
    ConversationManager → updates → ConversationState → triggers → UI updates
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from textual import on
from textual.containers import Container
from textual.message import Message

from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
)
from openhands_cli.tui.core.events import RequestSwitchConfirmation
from openhands_cli.tui.messages import UserInputSubmitted


if TYPE_CHECKING:
    from openhands_cli.tui.core.conversation_runner import ConversationRunner
    from openhands_cli.tui.core.state import ConversationState
    from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer

logger = logging.getLogger(__name__)


# Type alias for visualizer factory
VisualizerFactory = Callable[[uuid.UUID], "ConversationVisualizer"]


# ============================================================================
# Messages - Components post these to ConversationManager
# ============================================================================


class SendMessage(Message):
    """Request to send a user message to the current conversation."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content


class CreateConversation(Message):
    """Request to create a new conversation."""

    pass


class SwitchConversation(Message):
    """Request to switch to a different conversation."""

    def __init__(self, conversation_id: uuid.UUID) -> None:
        super().__init__()
        self.conversation_id = conversation_id


class PauseConversation(Message):
    """Request to pause the current running conversation."""

    pass


class CondenseConversation(Message):
    """Request to condense the current conversation history."""

    pass


class SetConfirmationPolicy(Message):
    """Request to change the confirmation policy."""

    def __init__(self, policy: ConfirmationPolicyBase) -> None:
        super().__init__()
        self.policy = policy


class SwitchConfirmed(Message):
    """Internal message: User confirmed switch in modal."""

    def __init__(self, target_id: uuid.UUID, confirmed: bool) -> None:
        super().__init__()
        self.target_id = target_id
        self.confirmed = confirmed


class _SwitchPrepare(Message):
    """Internal message to prepare switch on main thread."""

    def __init__(self, target_id: uuid.UUID) -> None:
        super().__init__()
        self.target_id = target_id


# ============================================================================
# ConversationManager - Handles conversation operations via events
# ============================================================================


class ConversationManager(Container):
    """Manages conversation lifecycle and operations.

    ConversationManager is a Container that wraps the content area and:
    - Receives operation messages that bubble up from child components
    - Manages ConversationRunner instances
    - Updates ConversationState with results (reactive UI updates)
    - Calls app methods directly (notify, run_worker)

    Reactive UI:
        State changes in ConversationState trigger automatic UI updates:
        - conversation_id=None: InputField disables (switching in progress)
        - conversation_id=UUID: UI components refresh for new conversation
        - running: Status line updates

    Events (minimal):
        - RequestSwitchConfirmation: App shows modal, returns SwitchConfirmed

    Widget Hierarchy:
        OpenHandsApp
        └── ConversationManager (Container) ← Messages bubble here
            └── Horizontal(#content_area)
                └── ConversationState ← Owns reactive state for data_bind
                    └── InputAreaContainer, etc.

    Example:
        # In InputAreaContainer - messages bubble up naturally:
        self.post_message(CreateConversation())

        # UserInputSubmitted from InputField also bubbles up here
    """

    def __init__(
        self,
        state: "ConversationState",
        *,
        visualizer_factory: VisualizerFactory | None = None,
        confirmation_callback: Callable | None = None,
        env_overrides_enabled: bool = False,
        critic_disabled: bool = False,
        json_mode: bool = False,
        headless_mode: bool = False,
    ) -> None:
        """Initialize the conversation manager.

        Args:
            state: The ConversationState to update with operation results.
            visualizer_factory: Factory function to create visualizers. If None,
                a default factory using app references will be created on first use.
            confirmation_callback: Callback for handling action confirmations.
                If None, will be obtained from app on first use.
            env_overrides_enabled: If True, environment variables override
                stored settings.
            critic_disabled: If True, critic functionality is disabled.
            json_mode: If True, enable JSON output mode.
            headless_mode: If True, running in headless mode.
        """
        super().__init__()
        self._state = state
        self._visualizer_factory = visualizer_factory
        self._confirmation_callback = confirmation_callback
        self._env_overrides_enabled = env_overrides_enabled
        self._critic_disabled = critic_disabled
        self._json_mode = json_mode
        self._headless_mode = headless_mode

        # Runner registry - maps conversation_id to runner
        self._runners: dict[uuid.UUID, ConversationRunner] = {}
        self._current_runner: ConversationRunner | None = None

    # ---- Properties ----

    @property
    def state(self) -> "ConversationState":
        """Get the conversation state."""
        return self._state

    @property
    def current_runner(self) -> "ConversationRunner | None":
        """Get the current conversation runner."""
        return self._current_runner

    # ---- Helper Methods ----

    def _post_event(self, event: Message) -> None:
        """Post an event, handling cross-thread calls safely."""
        try:
            self.app.call_from_thread(lambda: self.post_message(event))
        except RuntimeError:
            # Already on main thread
            self.post_message(event)

    def _remove_confirmation_panel(self) -> None:
        """Remove inline confirmation panel if present."""
        from openhands_cli.tui.textual_app import OpenHandsApp

        app = self.app
        if isinstance(app, OpenHandsApp) and app.confirmation_panel:
            app.confirmation_panel.remove()
            app.confirmation_panel = None

    # ---- Message Handlers ----

    @on(UserInputSubmitted)
    async def _on_user_input_submitted(self, event: UserInputSubmitted) -> None:
        """Handle UserInputSubmitted from InputField."""
        event.stop()
        await self._process_user_message(event.content)

    @on(SendMessage)
    async def _on_send_message(self, event: SendMessage) -> None:
        """Handle SendMessage posted directly to ConversationManager."""
        event.stop()
        await self._process_user_message(event.content)

    async def _process_user_message(self, content: str) -> None:
        """Process a user message - render it and send to runner."""
        # Guard: no conversation_id means switching in progress
        if self._state.conversation_id is None:
            return

        # Get or create runner for current conversation
        runner = self._get_or_create_runner(self._state.conversation_id)

        # Render user message (also dismisses pending feedback widgets)
        runner.visualizer.render_user_message(content)

        # Update conversation title (for history panel)
        self._state.set_conversation_title(content)

        # If already running, queue the message
        if runner.is_running:
            await runner.queue_message(content)
            return

        # Process message asynchronously
        self.run_worker(
            runner.process_message_async(content, self._headless_mode),
            name="process_message",
        )

    @on(CreateConversation)
    def _on_create_conversation(self, event: CreateConversation) -> None:
        """Handle request to create a new conversation."""
        event.stop()

        from openhands_cli.conversations.store.local import LocalFileStore

        # Check if a conversation is currently running
        if self._state.running:
            self.app.notify(
                "Cannot start a new conversation while one is running. "
                "Please wait for the current conversation to complete or pause it.",
                title="New Conversation Error",
                severity="error",
            )
            return

        # Create new conversation in store
        store = LocalFileStore()
        new_id_str = store.create()
        new_id = uuid.UUID(new_id_str)

        # Reset current runner
        self._current_runner = None

        # Update state - triggers reactive UI updates
        self._state.reset_conversation_state()
        self._state.conversation_id = new_id

        # Remove any existing confirmation panel
        self._remove_confirmation_panel()

        # Notify about new conversation
        self.app.notify(
            "Started a new conversation",
            title="New Conversation",
            severity="information",
        )

    @on(SwitchConversation)
    def _on_switch_conversation(self, event: SwitchConversation) -> None:
        """Handle request to switch to a different conversation."""
        event.stop()

        target_id = event.conversation_id

        # Don't switch if already on this conversation
        if self._state.conversation_id == target_id:
            self.app.notify(
                "This conversation is already active.",
                title="Already Active",
                severity="information",
            )
            return

        # If agent is running, request confirmation modal (App handles this)
        if self._state.running:
            self.post_message(RequestSwitchConfirmation(target_id))
            return

        # Perform the switch
        self._perform_switch(target_id)

    @on(SwitchConfirmed)
    def _on_switch_confirmed(self, event: SwitchConfirmed) -> None:
        """Handle switch confirmation result from modal."""
        event.stop()

        if event.confirmed:
            self._perform_switch(event.target_id, pause_current=True)
        # If cancelled, no state changes needed - start_switching() wasn't called yet

    def _perform_switch(
        self, target_id: uuid.UUID, *, pause_current: bool = False
    ) -> None:
        """Perform the conversation switch.

        Reactive behaviors handled by state changes:
        - conversation_id=None -> InputField disables
        - conversation_id=target_id -> InputField enables and focuses
        """
        # Update state - triggers reactive UI updates (input disabled)
        self._state.start_switching()

        # Run switch in background thread
        def _switch_worker() -> None:
            # Pause current runner if needed
            if (
                pause_current
                and self._current_runner
                and self._current_runner.is_running
            ):
                self._current_runner.conversation.pause()

            # Prepare switch on main thread
            self._post_event(_SwitchPrepare(target_id))

        self.run_worker(
            _switch_worker,
            name="switch_conversation",
            group="switch_conversation",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    @on(_SwitchPrepare)
    def _on_switch_prepare(self, event: "_SwitchPrepare") -> None:
        """Prepare UI for switch (runs on main thread)."""
        event.stop()
        target_id = event.target_id

        # Reset state for new conversation (conversation_id still None)
        self._state.reset_conversation_state()

        # Clear current runner, will be created on next message
        self._current_runner = None

        # Remove confirmation panel if present
        self._remove_confirmation_panel()

        # Get or create runner for new conversation
        self._current_runner = self._get_or_create_runner(target_id)

        # Finish switch - sets conversation_id, triggers reactive UI updates
        self._finish_switch(target_id)

    def _finish_switch(self, target_id: uuid.UUID) -> None:
        """Finalize the switch.

        Setting conversation_id triggers reactive behaviors:
        - InputField re-enables and focuses
        """
        # Update state - triggers reactive UI updates
        self._state.finish_switching(target_id)

        # Notify user
        self.app.notify(
            f"Resumed conversation {target_id.hex[:8]}",
            title="Switched",
            severity="information",
        )

    @on(PauseConversation)
    async def _on_pause_conversation(self, event: PauseConversation) -> None:
        """Handle request to pause the current conversation."""
        event.stop()

        if self._current_runner and self._current_runner.is_running:
            self.app.notify(
                "Pausing conversation, this may take a few seconds...",
                title="Pausing conversation",
                severity="information",
            )
            await asyncio.to_thread(self._current_runner.conversation.pause)
        else:
            self.app.notify(
                "No running conversation to pause",
                severity="error",
            )

    @on(CondenseConversation)
    async def _on_condense_conversation(self, event: CondenseConversation) -> None:
        """Handle request to condense conversation history."""
        event.stop()

        if not self._current_runner:
            self.app.notify(
                "No conversation available to condense",
                title="Condense Error",
                severity="error",
            )
            return

        if self._current_runner.is_running:
            self.app.notify(
                "Cannot condense while conversation is running.",
                title="Condense Error",
                severity="warning",
            )
            return

        try:
            self.app.notify(
                "Conversation condensation will be completed shortly...",
                title="Condensation Started",
                severity="information",
            )
            await asyncio.to_thread(self._current_runner.conversation.condense)
            self.app.notify(
                "Conversation history has been condensed successfully",
                title="Condensation Complete",
                severity="information",
            )
        except Exception as e:
            self.app.notify(
                f"Failed to condense conversation: {str(e)}",
                title="Condensation Error",
                severity="error",
            )

    @on(SetConfirmationPolicy)
    def _on_set_confirmation_policy(self, event: SetConfirmationPolicy) -> None:
        """Handle request to change confirmation policy."""
        event.stop()

        # Update conversation directly if we have a runner
        if self._current_runner and self._current_runner.conversation:
            self._current_runner.conversation.set_confirmation_policy(event.policy)

        # Update state for UI (triggers reactive updates)
        self._state.confirmation_policy = event.policy

    # ---- Runner Management ----

    def _get_or_create_runner(self, conversation_id: uuid.UUID) -> "ConversationRunner":
        """Get existing runner or create a new one."""
        if conversation_id in self._runners:
            runner = self._runners[conversation_id]
            self._current_runner = runner
            return runner

        runner = self._create_runner(conversation_id)
        self._runners[conversation_id] = runner
        self._current_runner = runner
        return runner

    def _create_runner(self, conversation_id: uuid.UUID) -> "ConversationRunner":
        """Create a new ConversationRunner for the given conversation."""
        from openhands_cli.tui.core.conversation_runner import ConversationRunner
        from openhands_cli.utils import json_callback

        # Use injected factory or create default
        if self._visualizer_factory:
            visualizer = self._visualizer_factory(conversation_id)
        else:
            # Fallback: create visualizer directly (for backwards compat)
            # Import here to avoid circular import
            from openhands_cli.tui.textual_app import OpenHandsApp
            from openhands_cli.tui.widgets.richlog_visualizer import (
                ConversationVisualizer,
            )

            app = self.app
            if isinstance(app, OpenHandsApp):
                visualizer = ConversationVisualizer(
                    app.scroll_view,
                    app,
                    skip_user_messages=True,
                    name="OpenHands Agent",
                )
            else:
                raise RuntimeError(
                    "visualizer_factory must be provided when not using OpenHandsApp"
                )

        # Create JSON callback if in JSON mode
        event_callback = json_callback if self._json_mode else None

        # Use injected callback or get from app
        confirmation_callback = self._confirmation_callback
        if confirmation_callback is None:
            from openhands_cli.tui.textual_app import OpenHandsApp

            app = self.app
            if isinstance(app, OpenHandsApp):
                confirmation_callback = app._handle_confirmation_request
            else:
                # Default no-op callback
                from openhands_cli.user_actions.types import UserConfirmation

                def default_confirmation_callback(_: list) -> UserConfirmation:
                    return UserConfirmation.ACCEPT

                confirmation_callback = default_confirmation_callback

        # Create notification callback that calls app.notify directly
        from textual.notifications import SeverityLevel

        def notification_callback(
            title: str, message: str, severity: SeverityLevel
        ) -> None:
            # Use call_from_thread since this may be called from background thread
            self.app.call_from_thread(
                lambda: self.app.notify(message, title=title, severity=severity)
            )

        # Create runner
        runner = ConversationRunner(
            conversation_id,
            state=self._state,
            message_pump=self,
            confirmation_callback=confirmation_callback,
            notification_callback=notification_callback,
            visualizer=visualizer,
            event_callback=event_callback,
            env_overrides_enabled=self._env_overrides_enabled,
            critic_disabled=self._critic_disabled,
        )

        # Attach conversation to state for metrics reading
        self._state.attach_conversation(runner.conversation)

        return runner

    # ---- Public API for direct calls ----

    async def send_message(self, content: str) -> None:
        """Send a message to the current conversation."""
        self.post_message(SendMessage(content))

    def create_conversation(self) -> None:
        """Create a new conversation."""
        self.post_message(CreateConversation())

    def switch_conversation(self, conversation_id: uuid.UUID) -> None:
        """Switch to a different conversation."""
        self.post_message(SwitchConversation(conversation_id))

    def pause_conversation(self) -> None:
        """Pause the current conversation."""
        self.post_message(PauseConversation())

    def reload_visualizer_configuration(self) -> None:
        """Reload the visualizer configuration for the current conversation."""
        if self._current_runner:
            self._current_runner.visualizer.reload_configuration()
