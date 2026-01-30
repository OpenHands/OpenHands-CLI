"""ConversationManager - centralized conversation operations handler.

This module provides ConversationManager, which handles all conversation
operations including creating, switching, and sending messages. It decouples
business logic from UI state management.

Architecture:
    ConversationManager is a Container that wraps the content area. Messages
    from child components (InputField, InputAreaContainer, HistorySidePanel)
    bubble up through the DOM tree and are handled here.

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
from typing import TYPE_CHECKING, cast

from textual import on
from textual.containers import Container
from textual.message import Message

from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
)
from openhands_cli.tui.messages import UserInputSubmitted


if TYPE_CHECKING:
    from openhands_cli.tui.core.conversation_runner import ConversationRunner
    from openhands_cli.tui.core.state import ConversationState
    from openhands_cli.tui.textual_app import OpenHandsApp

logger = logging.getLogger(__name__)


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


# ============================================================================
# ConversationManager - Hidden widget that handles conversation operations
# ============================================================================


class ConversationManager(Container):
    """Manages conversation lifecycle and operations.

    ConversationManager is a Container that wraps the content area and:
    - Receives operation messages that bubble up from child components
    - Manages ConversationRunner instances
    - Updates ConversationState with results
    - Coordinates with external services (LocalFileStore, SDK)

    Because ConversationManager is an ancestor of UI components, messages
    naturally bubble up to it. Components can simply use self.post_message()
    instead of explicitly targeting the manager.

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
        env_overrides_enabled: bool = False,
        critic_disabled: bool = False,
        json_mode: bool = False,
    ) -> None:
        """Initialize the conversation manager.

        Args:
            state: The ConversationState to update with operation results.
            env_overrides_enabled: If True, environment variables override
                stored settings.
            critic_disabled: If True, critic functionality is disabled.
            json_mode: If True, enable JSON output mode.
        """
        super().__init__()
        self._state = state
        self._env_overrides_enabled = env_overrides_enabled
        self._critic_disabled = critic_disabled
        self._json_mode = json_mode

        # Runner registry - maps conversation_id to runner
        self._runners: dict[uuid.UUID, ConversationRunner] = {}
        self._current_runner: ConversationRunner | None = None

        # Switch coordination
        self._loading_notification = None

    # ---- Properties ----

    @property
    def state(self) -> "ConversationState":
        """Get the conversation state."""
        return self._state

    @property
    def current_runner(self) -> "ConversationRunner | None":
        """Get the current conversation runner."""
        return self._current_runner

    # ---- Message Handlers ----

    @on(UserInputSubmitted)
    async def _on_user_input_submitted(self, event: UserInputSubmitted) -> None:
        """Handle UserInputSubmitted from InputField.

        This handles the bubbled message from InputField when user submits text.
        """
        event.stop()
        await self._process_user_message(event.content)

    @on(SendMessage)
    async def _on_send_message(self, event: SendMessage) -> None:
        """Handle SendMessage posted directly to ConversationManager.

        This is for programmatic use (e.g., queued inputs from --task).
        """
        event.stop()
        await self._process_user_message(event.content)

    async def _process_user_message(self, content: str) -> None:
        """Process a user message - render it and send to runner."""

        app = cast("OpenHandsApp", self.app)

        # Get or create runner for current conversation
        runner = self._get_or_create_runner(self._state.conversation_id)

        # Render user message via the visualizer
        runner.visualizer.render_user_message(content)

        # Dismiss any pending critic feedback widgets
        self._dismiss_pending_feedback_widgets()

        # Update conversation title (for history panel)
        self._state.set_conversation_title(content)

        # If already running, queue the message
        if runner.is_running:
            await runner.queue_message(content)
            return

        # Process message asynchronously
        app.run_worker(
            runner.process_message_async(content, app.headless_mode),
            name="process_message",
        )

    @on(CreateConversation)
    def _on_create_conversation(self, event: CreateConversation) -> None:
        """Handle request to create a new conversation."""
        event.stop()

        from openhands_cli.conversations.store.local import LocalFileStore

        app = cast("OpenHandsApp", self.app)

        # Check if a conversation is currently running
        if self._state.running:
            app.notify(
                title="New Conversation Error",
                message="Cannot start a new conversation while one is running. "
                "Please wait for the current conversation to complete or pause it.",
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
        if app.confirmation_panel:
            app.confirmation_panel.remove()
            app.confirmation_panel = None

        app.notify(
            title="New Conversation",
            message="Started a new conversation",
            severity="information",
        )

    @on(SwitchConversation)
    def _on_switch_conversation(self, event: SwitchConversation) -> None:
        """Handle request to switch to a different conversation."""
        event.stop()

        from openhands_cli.tui.modals import SwitchConversationModal

        app = cast("OpenHandsApp", self.app)
        target_id = event.conversation_id

        # Don't switch if already on this conversation
        if self._state.conversation_id == target_id:
            app.notify(
                title="Already Active",
                message="This conversation is already active.",
                severity="information",
            )
            return

        # If agent is running, show confirmation modal
        if self._state.running:
            app.push_screen(
                SwitchConversationModal(
                    prompt=(
                        "The agent is still running.\n\n"
                        "Switching conversations will pause the current run.\n"
                        "Do you want to switch anyway?"
                    )
                ),
                lambda confirmed: self._handle_switch_confirmation(
                    confirmed, target_id
                ),
            )
            return

        # Perform the switch
        self._perform_switch(target_id)

    def _handle_switch_confirmation(
        self, confirmed: bool | None, target_id: uuid.UUID
    ) -> None:
        """Handle result of switch confirmation modal."""
        if confirmed:
            self._perform_switch(target_id, pause_current=True)
        else:
            # Revert switching state
            self._state.finish_switching()
            app = cast("OpenHandsApp", self.app)
            app.input_field.focus_input()

    def _perform_switch(
        self, target_id: uuid.UUID, *, pause_current: bool = False
    ) -> None:
        """Perform the conversation switch."""
        from textual.notifications import Notification, Notify

        app = cast("OpenHandsApp", self.app)

        # Show loading notification
        self._state.start_switching()
        notification = Notification(
            "⏳ Switching conversation...",
            title="Switching",
            severity="information",
            timeout=3600,
            markup=True,
        )
        self._loading_notification = notification
        app.post_message(Notify(notification))

        # Disable input during switch
        app.input_field.disabled = True

        # Run switch in background thread
        def _switch_worker() -> None:
            # Pause current runner if needed
            if (
                pause_current
                and self._current_runner
                and self._current_runner.is_running
            ):
                self._current_runner.conversation.pause()

            # Prepare UI on main thread
            app.call_from_thread(self._prepare_switch_ui, target_id)

        app.run_worker(
            _switch_worker,
            name="switch_conversation",
            group="switch_conversation",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _prepare_switch_ui(self, target_id: uuid.UUID) -> None:
        """Prepare UI for switch (runs on main thread)."""

        app = cast("OpenHandsApp", self.app)

        # Update state - triggers reactive updates
        self._state.conversation_id = target_id
        self._state.reset_conversation_state()

        # Clear current runner, will be created on next message
        self._current_runner = None

        # Remove confirmation panel if present
        if app.confirmation_panel:
            app.confirmation_panel.remove()
            app.confirmation_panel = None

        # Get or create runner for new conversation
        self._current_runner = self._get_or_create_runner(target_id)

        # Finish switch
        self._finish_switch(target_id)

    def _finish_switch(self, target_id: uuid.UUID) -> None:
        """Finalize the switch (runs on main thread)."""

        app = cast("OpenHandsApp", self.app)

        # Dismiss loading notification
        if self._loading_notification:
            try:
                app._unnotify(self._loading_notification)
            except Exception:
                pass
            self._loading_notification = None

        self._state.finish_switching()

        app.scroll_view.scroll_end(animate=False)
        app.notify(
            title="Switched",
            message=f"Resumed conversation {target_id.hex[:8]}",
            severity="information",
        )
        app.input_field.disabled = False
        app.input_field.focus_input()

    @on(PauseConversation)
    async def _on_pause_conversation(self, event: PauseConversation) -> None:
        """Handle request to pause the current conversation."""
        event.stop()

        app = cast("OpenHandsApp", self.app)

        if self._current_runner and self._current_runner.is_running:
            app.notify(
                title="Pausing conversation",
                message="Pausing conversation, this may take a few seconds...",
                severity="information",
            )
            await asyncio.to_thread(self._current_runner.conversation.pause)
        else:
            app.notify(
                message="No running conversation to pause",
                severity="error",
            )

    @on(CondenseConversation)
    async def _on_condense_conversation(self, event: CondenseConversation) -> None:
        """Handle request to condense conversation history."""
        event.stop()

        app = cast("OpenHandsApp", self.app)

        if not self._current_runner:
            app.notify(
                title="Condense Error",
                message="No conversation available to condense",
                severity="error",
            )
            return

        if self._current_runner.is_running:
            app.notify(
                title="Condense Error",
                message="Cannot condense while conversation is running.",
                severity="warning",
            )
            return

        try:
            app.notify(
                title="Condensation Started",
                message="Conversation condensation will be completed shortly...",
                severity="information",
            )
            await asyncio.to_thread(self._current_runner.conversation.condense)
            app.notify(
                title="Condensation Complete",
                message="Conversation history has been condensed successfully",
                severity="information",
            )
        except Exception as e:
            app.notify(
                title="Condensation Error",
                message=f"Failed to condense conversation: {str(e)}",
                severity="error",
            )

    @on(SetConfirmationPolicy)
    def _on_set_confirmation_policy(self, event: SetConfirmationPolicy) -> None:
        """Handle request to change confirmation policy.

        Updates both:
        1. The conversation object directly (if runner exists)
        2. The state for UI binding
        """
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
        from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer
        from openhands_cli.utils import json_callback

        app = cast("OpenHandsApp", self.app)

        # Create visualizer
        conversation_visualizer = ConversationVisualizer(
            app.scroll_view, app, skip_user_messages=True, name="OpenHands Agent"
        )

        # Create JSON callback if in JSON mode
        event_callback = json_callback if self._json_mode else None

        # Create runner
        # - state: for reading state (is_confirmation_active) and updating (set_running)
        # - message_pump: self (ConversationManager) for posting policy change messages
        runner = ConversationRunner(
            conversation_id,
            state=self._state,
            message_pump=self,  # ConversationManager is a MessagePump
            confirmation_callback=app._handle_confirmation_request,
            notification_callback=lambda title, message, severity: (
                app.notify(title=title, message=message, severity=severity)
            ),
            visualizer=conversation_visualizer,
            event_callback=event_callback,
            env_overrides_enabled=self._env_overrides_enabled,
            critic_disabled=self._critic_disabled,
        )

        # Attach conversation to state for metrics reading
        self._state.attach_conversation(runner.conversation)

        return runner

    def _dismiss_pending_feedback_widgets(self) -> None:
        """Remove all pending CriticFeedbackWidget instances."""
        from openhands_cli.tui.utils.critic.feedback import CriticFeedbackWidget

        app = cast("OpenHandsApp", self.app)

        for widget in app.scroll_view.query(CriticFeedbackWidget):
            widget.remove()

    # ---- Public API for direct calls ----

    async def send_message(self, content: str) -> None:
        """Send a message to the current conversation.

        This is a convenience method for programmatic use.
        """
        self.post_message(SendMessage(content))

    def create_conversation(self) -> None:
        """Create a new conversation.

        This is a convenience method for programmatic use.
        """
        self.post_message(CreateConversation())

    def switch_conversation(self, conversation_id: uuid.UUID) -> None:
        """Switch to a different conversation.

        This is a convenience method for programmatic use.
        """
        self.post_message(SwitchConversation(conversation_id))

    def pause_conversation(self) -> None:
        """Pause the current conversation.

        This is a convenience method for programmatic use.
        """
        self.post_message(PauseConversation())

    def reload_visualizer_configuration(self) -> None:
        """Reload the visualizer configuration for the current conversation.

        This is used when settings change and the visualizer needs to
        update its configuration.
        """
        if self._current_runner:
            self._current_runner.visualizer.reload_configuration()
