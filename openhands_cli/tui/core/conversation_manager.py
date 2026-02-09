"""ConversationManager - thin Textual message router for conversations.

ConversationManager is intentionally small: it listens to a handful of Textual
messages bubbling up from child widgets and delegates the actual work to focused
controllers/services.

It is the integration point between Textual's message system and the TUI core
business logic (runner lifecycle, CRUD/store interactions, switching flows,
confirmation policy + resume flows, etc.).
"""

import uuid
from typing import TYPE_CHECKING

from textual import on
from textual.containers import Container
from textual.message import Message

from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase
from openhands_cli.conversations.protocols import ConversationStore
from openhands_cli.tui.core.confirmation_flow_controller import (
    ConfirmationFlowController,
)
from openhands_cli.tui.core.confirmation_policy_service import (
    ConfirmationPolicyService,
)
from openhands_cli.tui.core.conversation_crud_controller import (
    ConversationCrudController,
)
from openhands_cli.tui.core.conversation_switch_controller import (
    ConversationSwitchController,
)
from openhands_cli.tui.core.events import ConfirmationDecision, ShowConfirmationPanel
from openhands_cli.tui.core.runner_factory import RunnerFactory
from openhands_cli.tui.core.runner_registry import RunnerRegistry
from openhands_cli.tui.core.user_message_controller import UserMessageController
from openhands_cli.tui.messages import UserInputSubmitted


if TYPE_CHECKING:
    from openhands_cli.tui.core.conversation_runner import ConversationRunner
    from openhands_cli.tui.core.state import ConversationContainer


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


# ============================================================================
# ConversationManager - Handles conversation operations via events
# ============================================================================


class ConversationManager(Container):
    """Textual event handler that delegates conversation responsibilities.

    This widget owns no business logic beyond:
    - stopping/ack'ing messages, and
    - routing them to the appropriate controller/service.

    The core responsibilities are split into:
    - RunnerRegistry / RunnerFactory: runner creation + lifecycle
    - ConversationCrudController: create/reset
    - ConversationSwitchController: switching + switch-confirmation orchestration
    - UserMessageController: rendering + message send/queue behavior
    - ConfirmationPolicyService + ConfirmationFlowController: policy + resume flows
    """

    def __init__(
        self,
        state: "ConversationContainer",
        *,
        runner_factory: RunnerFactory,
        store_service: ConversationStore,
        headless_mode: bool = False,
    ) -> None:
        super().__init__()
        self._state = state
        self._headless_mode = headless_mode
        self._store_service = store_service

        from textual.notifications import SeverityLevel

        def notification_callback(
            title: str, message: str, severity: SeverityLevel
        ) -> None:
            self.notify(message, title=title, severity=severity)

        self._runners = RunnerRegistry(
            factory=runner_factory,
            state=self._state,
            message_pump=self,
            notification_callback=notification_callback,
        )

        self._policy_service = ConfirmationPolicyService(
            state=self._state,
            runners=self._runners,
        )

        self._message_controller = UserMessageController(
            state=self._state,
            runners=self._runners,
            run_worker=self.run_worker,
            headless_mode=self._headless_mode,
        )
        self._crud_controller = ConversationCrudController(
            state=self._state,
            store=self._store_service,
            runners=self._runners,
            notify=self.notify,
        )
        self._switch_controller = ConversationSwitchController(
            state=self._state,
            runners=self._runners,
            notify=self.notify,
            post_message=self.post_message,
            run_worker=self.run_worker,
            call_from_thread=lambda func, *args: self.app.call_from_thread(func, *args),
        )
        self._confirmation_controller = ConfirmationFlowController(
            state=self._state,
            runners=self._runners,
            policy_service=self._policy_service,
            run_worker=self.run_worker,
        )

    # ---- Properties ----

    @property
    def state(self) -> "ConversationContainer":
        """Get the conversation state."""
        return self._state

    @property
    def current_runner(self) -> "ConversationRunner | None":
        """Get the current conversation runner."""
        return self._runners.current

    # ---- Message Handlers ----

    @on(UserInputSubmitted)
    async def _on_user_input_submitted(self, event: UserInputSubmitted) -> None:
        """Handle UserInputSubmitted from InputField."""
        event.stop()
        await self._message_controller.handle_user_message(event.content)

    @on(SendMessage)
    async def _on_send_message(self, event: SendMessage) -> None:
        """Handle SendMessage posted directly to ConversationManager."""
        event.stop()
        await self._message_controller.handle_user_message(event.content)

    @on(CreateConversation)
    def _on_create_conversation(self, event: CreateConversation) -> None:
        """Handle request to create a new conversation."""
        event.stop()
        self._crud_controller.create_conversation()

    @on(SwitchConversation)
    def _on_switch_conversation(self, event: SwitchConversation) -> None:
        """Handle request to switch to a different conversation."""
        event.stop()
        self._switch_controller.request_switch(event.conversation_id)

    @on(SwitchConfirmed)
    def _on_switch_confirmed(self, event: SwitchConfirmed) -> None:
        """Handle switch confirmation result from modal."""
        event.stop()
        self._switch_controller.handle_switch_confirmed(
            event.target_id,
            confirmed=event.confirmed,
        )

    @on(PauseConversation)
    async def _on_pause_conversation(self, event: PauseConversation) -> None:
        """Handle request to pause the current conversation."""
        event.stop()

        runner = self._runners.current
        if runner is None:
            self.notify("No running conversation to pause", severity="error")
            return

        await runner.pause()

    @on(CondenseConversation)
    async def _on_condense_conversation(self, event: CondenseConversation) -> None:
        """Handle request to condense conversation history."""
        event.stop()

        runner = self._runners.current
        if runner is None:
            self.notify(
                "No conversation available to condense",
                title="Condense Error",
                severity="error",
            )
            return

        await runner.condense_async()

    @on(SetConfirmationPolicy)
    def _on_set_confirmation_policy(self, event: SetConfirmationPolicy) -> None:
        """Handle request to change confirmation policy."""
        event.stop()
        self._policy_service.set_policy(event.policy)

    @on(ShowConfirmationPanel)
    def _on_show_confirmation_panel(self, event: ShowConfirmationPanel) -> None:
        event.stop()
        self._confirmation_controller.show_panel(len(event.pending_actions))

    @on(ConfirmationDecision)
    def _on_confirmation_decision(self, event: ConfirmationDecision) -> None:
        event.stop()
        self._confirmation_controller.handle_decision(event.decision)

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
        runner = self._runners.current
        if runner is not None:
            runner.visualizer.reload_configuration()
