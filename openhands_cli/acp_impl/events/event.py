"""Utility functions for ACP implementation."""

from acp import (
    Client,
    update_agent_message_text,
    update_agent_thought_text,
)

from openhands.sdk import BaseConversation, get_logger
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    Condensation,
    CondensationRequest,
    ConversationStateUpdateEvent,
    Event,
    MessageEvent,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
    UserRejectObservation,
)
from openhands_cli.acp_impl.events.shared_event_handler import (
    REASONING_HEADER,
    THOUGHT_HEADER,
    SharedEventHandler,
    _event_visualize_to_plain,
)
from openhands_cli.acp_impl.events.utils import (
    get_metadata,
)


logger = get_logger(__name__)


class EventSubscriber:
    """Subscriber for handling OpenHands events and converting them to ACP
    notifications.

    This class subscribes to events from an OpenHands conversation and converts
    them to ACP session update notifications that are streamed back to the client.
    """

    def __init__(
        self,
        session_id: str,
        conn: "Client",
        conversation: BaseConversation | None = None,
    ):
        """Initialize the event subscriber.

        Args:
            session_id: The ACP session ID
            conn: The ACP connection for sending notifications
            conversation: Optional conversation instance for accessing metrics
        """
        self.session_id = session_id
        self.conn = conn
        self.conversation = conversation
        self.shared_events_handler = SharedEventHandler()

    async def __call__(self, event: Event):
        """Handle incoming events and convert them to ACP notifications.

        Args:
            event: Event to process (ActionEvent, ObservationEvent, etc.)
        """
        # Skip ConversationStateUpdateEvent (internal state management)
        if isinstance(event, ConversationStateUpdateEvent):
            return

        # Handle different event types
        if isinstance(event, ActionEvent):
            await self._handle_action_event(event)
        elif isinstance(event, UserRejectObservation) or isinstance(
            event, AgentErrorEvent
        ):
            await self.shared_events_handler.handle_user_reject_or_agent_error(
                self, event
            )
        elif isinstance(event, ObservationEvent):
            await self.shared_events_handler.handle_observation(self, event)
        elif isinstance(event, MessageEvent):
            await self._handle_message_event(event)
        elif isinstance(event, SystemPromptEvent):
            await self.shared_events_handler.handle_system_prompt(self, event)
        elif isinstance(event, PauseEvent):
            await self.shared_events_handler.handle_pause(self, event)
        elif isinstance(event, Condensation):
            await self.shared_events_handler.handle_condensation(self, event)
        elif isinstance(event, CondensationRequest):
            await self.shared_events_handler.handle_condensation_request(self, event)

    async def _handle_action_event(self, event: ActionEvent):
        """Handle ActionEvent: send thought as agent_message_chunk, then tool_call.

        Args:
            event: ActionEvent to process
        """
        try:
            # First, send thoughts/reasoning as agent_message_chunk if available
            thought_text = " ".join([t.text for t in event.thought])

            if event.reasoning_content and event.reasoning_content.strip():
                await self.conn.session_update(
                    session_id=self.session_id,
                    update=update_agent_thought_text(
                        REASONING_HEADER + event.reasoning_content.strip() + "\n"
                    ),
                    field_meta=get_metadata(self.conversation),
                )

            if thought_text.strip():
                await self.conn.session_update(
                    session_id=self.session_id,
                    update=update_agent_thought_text(
                        THOUGHT_HEADER + thought_text.strip() + "\n"
                    ),
                    field_meta=get_metadata(self.conversation),
                )

            # Generate content for the tool call
            await self.shared_events_handler.handle_action_event(self, event)
        except Exception as e:
            logger.debug(f"Error processing ActionEvent: {e}", exc_info=True)

    async def _handle_message_event(self, event: MessageEvent):
        """Handle MessageEvent by sending AgentMessageChunk or UserMessageChunk.

        Args:
            event: MessageEvent from agent or user
        """
        try:
            # Get visualization text
            viz_text = _event_visualize_to_plain(event)
            if not viz_text.strip():
                return

            # Determine which type of message chunk to send based on role
            if event.llm_message.role == "user":
                # NOTE: Zed UI will render user messages when it is sent
                # if we update it again, they will be duplicated
                pass
            else:  # assistant or other roles
                await self.conn.session_update(
                    session_id=self.session_id,
                    update=update_agent_message_text(viz_text),
                    field_meta=get_metadata(self.conversation),
                )
        except Exception as e:
            logger.debug(f"Error processing MessageEvent: {e}", exc_info=True)
