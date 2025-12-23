"""Utility functions for ACP implementation."""

from acp import Client
from acp.schema import (
    AgentMessageChunk,
    AgentThoughtChunk,
    ContentToolCallContent,
    FileEditToolCallContent,
    TerminalToolCallContent,
    TextContentBlock,
    ToolCallStart,
    ToolKind,
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
from openhands.sdk.tool.builtins.finish import FinishAction
from openhands.sdk.tool.builtins.think import ThinkAction
from openhands.tools.file_editor.definition import (
    FileEditorAction,
)
from openhands.tools.task_tracker.definition import (
    TaskTrackerAction,
)
from openhands.tools.terminal.definition import TerminalAction
from openhands_cli.acp_impl.events.shared_event_handler import (
    SharedEventHandler,
    _event_visualize_to_plain,
)
from openhands_cli.acp_impl.events.utils import (
    extract_action_locations,
    format_content_blocks,
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
                    update=AgentThoughtChunk(
                        session_update="agent_thought_chunk",
                        content=TextContentBlock(
                            type="text",
                            text="**Reasoning**:\n"
                            + event.reasoning_content.strip()
                            + "\n",
                        ),
                    ),
                    field_meta=get_metadata(self.conversation),
                )

            if thought_text.strip():
                await self.conn.session_update(
                    session_id=self.session_id,
                    update=AgentThoughtChunk(
                        session_update="agent_thought_chunk",
                        content=TextContentBlock(
                            type="text",
                            text="\n**Thought**:\n" + thought_text.strip() + "\n",
                        ),
                    ),
                    field_meta=get_metadata(self.conversation),
                )

            # Generate content for the tool call
            content: (
                list[
                    ContentToolCallContent
                    | FileEditToolCallContent
                    | TerminalToolCallContent
                ]
                | None
            ) = None
            tool_kind_mapping: dict[str, ToolKind] = {
                "terminal": "execute",
                "browser_use": "fetch",
                "browser": "fetch",
            }
            tool_kind = tool_kind_mapping.get(event.tool_name, "other")
            title = event.tool_name
            if event.action:
                action_viz = _event_visualize_to_plain(event)
                content = format_content_blocks(action_viz)

                if isinstance(event.action, FileEditorAction):
                    if event.action.command == "view":
                        tool_kind = "read"
                        title = f"Reading {event.action.path}"
                    else:
                        tool_kind = "edit"
                        title = f"Editing {event.action.path}"
                elif isinstance(event.action, TerminalAction):
                    title = f"{event.action.command}"
                elif isinstance(event.action, TaskTrackerAction):
                    title = "Plan updated"
                elif isinstance(event.action, ThinkAction):
                    await self.conn.session_update(
                        session_id=self.session_id,
                        update=AgentThoughtChunk(
                            session_update="agent_thought_chunk",
                            content=TextContentBlock(
                                type="text",
                                text=action_viz,
                            ),
                        ),
                        field_meta=get_metadata(self.conversation),
                    )
                    return
                elif isinstance(event.action, FinishAction):
                    await self.conn.session_update(
                        session_id=self.session_id,
                        update=AgentMessageChunk(
                            session_update="agent_message_chunk",
                            content=TextContentBlock(
                                type="text",
                                text=action_viz,
                            ),
                        ),
                        field_meta=get_metadata(self.conversation),
                    )
                    return

            await self.conn.session_update(
                session_id=self.session_id,
                update=ToolCallStart(
                    session_update="tool_call",
                    tool_call_id=event.tool_call_id,
                    title=title,
                    kind=tool_kind,
                    status="in_progress",
                    content=content,
                    locations=extract_action_locations(event.action)
                    if event.action
                    else None,
                    raw_input=event.action.model_dump() if event.action else None,
                ),
                field_meta=get_metadata(self.conversation),
            )
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
                    update=AgentMessageChunk(
                        session_update="agent_message_chunk",
                        content=TextContentBlock(
                            type="text",
                            text=viz_text,
                        ),
                    ),
                    field_meta=get_metadata(self.conversation),
                )
        except Exception as e:
            logger.debug(f"Error processing MessageEvent: {e}", exc_info=True)

    async def _handle_system_prompt_event(self, event: SystemPromptEvent):
        """Handle SystemPromptEvent by sending as AgentThoughtChunk.

        System prompts are internal setup, so we send them as thought chunks
        to indicate they're part of the agent's internal state.

        Args:
            event: SystemPromptEvent
        """
        try:
            viz_text = _event_visualize_to_plain(event)
            if not viz_text.strip():
                return

            await self.conn.session_update(
                session_id=self.session_id,
                update=AgentThoughtChunk(
                    session_update="agent_thought_chunk",
                    content=TextContentBlock(
                        type="text",
                        text=viz_text,
                    ),
                ),
                field_meta=get_metadata(self.conversation),
            )
        except Exception as e:
            logger.debug(f"Error processing SystemPromptEvent: {e}", exc_info=True)

    async def _handle_pause_event(self, event: PauseEvent):
        """Handle PauseEvent by sending as AgentThoughtChunk.

        Args:
            event: PauseEvent
        """
        try:
            viz_text = _event_visualize_to_plain(event)
            if not viz_text.strip():
                return

            await self.conn.session_update(
                session_id=self.session_id,
                update=AgentThoughtChunk(
                    session_update="agent_thought_chunk",
                    content=TextContentBlock(
                        type="text",
                        text=viz_text,
                    ),
                ),
                field_meta=get_metadata(self.conversation),
            )
        except Exception as e:
            logger.debug(f"Error processing PauseEvent: {e}", exc_info=True)

    async def _handle_condensation_event(self, event: Condensation):
        """Handle Condensation by sending as AgentThoughtChunk.

        Condensation events indicate memory management is happening, which is
        useful for the user to know but doesn't require special UI treatment.

        Args:
            event: Condensation event
        """
        try:
            viz_text = _event_visualize_to_plain(event)
            if not viz_text.strip():
                return

            await self.conn.session_update(
                session_id=self.session_id,
                update=AgentThoughtChunk(
                    session_update="agent_thought_chunk",
                    content=TextContentBlock(
                        type="text",
                        text=viz_text,
                    ),
                ),
                field_meta=get_metadata(self.conversation),
            )
        except Exception as e:
            logger.debug(f"Error processing Condensation: {e}", exc_info=True)

    async def _handle_condensation_request_event(self, event: CondensationRequest):
        """Handle CondensationRequest by sending as AgentThoughtChunk.

        Args:
            event: CondensationRequest event
        """
        try:
            viz_text = _event_visualize_to_plain(event)
            if not viz_text.strip():
                return

            await self.conn.session_update(
                session_id=self.session_id,
                update=AgentThoughtChunk(
                    session_update="agent_thought_chunk",
                    content=TextContentBlock(
                        type="text",
                        text=viz_text,
                    ),
                ),
                field_meta=get_metadata(self.conversation),
            )
        except Exception as e:
            logger.debug(f"Error processing CondensationRequest: {e}", exc_info=True)
