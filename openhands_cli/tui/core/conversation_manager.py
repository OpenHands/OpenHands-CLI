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
from openhands_cli.tui.core.refinement_controller import RefinementController
from openhands_cli.tui.core.runner_factory import RunnerFactory
from openhands_cli.tui.core.runner_registry import RunnerRegistry
from openhands_cli.tui.core.user_message_controller import UserMessageController
from openhands_cli.tui.messages import (
    CriticResultReceived,
    SendMessage,
    SendRefinementMessage,
)
from openhands_cli.tui.core.btw_interceptor import (
    BTW_COMMAND,
    BtwInterceptor,
    get_btw_store,
)


if TYPE_CHECKING:
    from openhands_cli.tui.core.conversation_runner import ConversationRunner
    from openhands_cli.tui.core.state import ConversationContainer


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
    - RefinementController: iterative refinement based on critic results
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

        self._refinement_controller = RefinementController(
            state=self._state,
            runners=self._runners,
            post_message=self.post_message,
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

        # Initialize BTW interceptor for side-channel questions
        # Note: api_client will be set when needed via set_api_client()
        self._btw_interceptor: BtwInterceptor | None = None
        self._api_client = None

    def set_api_client(self, api_client, server_url: str | None = None) -> None:
        """Set the API client for BTW functionality.

        Args:
            api_client: The API client instance for making requests.
            server_url: Optional server URL for the API.
        """
        self._api_client = api_client

        # Create the BTW interceptor with the conversation ID from state
        conversation_id = str(self._state.conversation_id) if self._state.conversation_id else None

        async def ask_agent_callback(conv_id: str, question: str) -> dict:
            """Callback to call the ask_agent API."""
            return await api_client.ask_agent(conv_id, question)

        self._btw_interceptor = BtwInterceptor(
            conversation_id=conversation_id,
            ask_agent_callback=ask_agent_callback,
            get_btw_store=get_btw_store,
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

    @on(SendMessage)
    async def _on_send_message(self, event: SendMessage) -> None:
        """Handle SendMessage - the primary entry point for user messages.

        This handler:
        1. Checks for /btw (side-channel) commands and handles them separately
        2. Resets the refinement iteration counter (new user turn)
        3. Delegates to UserMessageController for rendering and processing
        """
        event.stop()
        self._refinement_controller.reset_iteration()

        # Check for BTW (side-channel) command
        if self._btw_interceptor is not None:
            # Update conversation ID in case it changed
            self._btw_interceptor._conversation_id = (
                str(self._state.conversation_id) if self._state.conversation_id else None
            )
            result = self._btw_interceptor.process(event.content)

            if result.is_btw and result.entry_id:
                # Handle BTW command - call the API asynchronously
                self._handle_btw_message(event.content, result.question, result.entry_id)
                return  # Don't process as regular message

        await self._message_controller.handle_user_message(event.content)

    async def _handle_btw_message(
        self,
        original_message: str,
        question: str | None,
        entry_id: str,
    ) -> None:
        """Handle a BTW (side-channel) message by calling the ask_agent API.

        Args:
            original_message: The original user message.
            question: The extracted question.
            entry_id: The BTW entry ID.
        """
        if self._btw_interceptor is None:
            return

        try:
            conversation_id = str(self._state.conversation_id) if self._state.conversation_id else None
            if not conversation_id:
                await self._btw_interceptor.fail(entry_id, "No conversation ID")
                return

            response = await self._api_client.ask_agent(conversation_id, question)
            await self._btw_interceptor.resolve(entry_id, response.get("response", ""))

            # Notify user that BTW response is available
            self.notify(
                f"BTW response: {response.get('response', '')}",
                title="Side Channel Response",
            )
        except Exception as e:
            await self._btw_interceptor.fail(entry_id, str(e))
            self.notify(
                f"BTW failed: {e}",
                title="Error",
                severity="error",
            )

    @on(SendRefinementMessage)
    async def _on_send_refinement_message(self, event: SendRefinementMessage) -> None:
        """Handle SendRefinementMessage for iterative refinement.

        Unlike SendMessage, this uses render_refinement_message which
        preserves the iteration counter for proper refinement tracking.
        """
        event.stop()
        await self._message_controller.handle_refinement_message(event.content)

    @on(CriticResultReceived)
    def _on_critic_result_received(self, event: CriticResultReceived) -> None:
        """Handle CriticResultReceived from visualizer.

        Routes critic results to RefinementController for evaluation and
        potential triggering of iterative refinement.
        """
        event.stop()
        self._refinement_controller.handle_critic_result(event.critic_result)

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
