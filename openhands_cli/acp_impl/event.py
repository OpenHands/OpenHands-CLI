"""Utility functions for ACP implementation."""

from typing import TYPE_CHECKING

from acp import SessionNotification
from acp.schema import (
    AgentMessageChunk,
    AgentPlanUpdate,
    AgentThoughtChunk,
    ContentToolCallContent,
    FileEditToolCallContent,
    PlanEntry,
    PlanEntryStatus,
    TerminalToolCallContent,
    TextContentBlock,
    ToolCallLocation,
    ToolCallProgress,
    ToolCallStart,
    ToolCallStatus,
    ToolKind,
)

from openhands.sdk import Action
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    Condensation,
    CondensationRequest,
    ConversationStateUpdateEvent,
    Event,
    MessageEvent,
    ObservationBaseEvent,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
    UserRejectObservation,
)


if TYPE_CHECKING:
    from acp import AgentSideConnection


from openhands.sdk import get_logger
from openhands.sdk.tool.builtins.finish import FinishAction, FinishObservation
from openhands.sdk.tool.builtins.think import ThinkAction, ThinkObservation
from openhands.tools.file_editor.definition import (
    FileEditorAction,
)
from openhands.tools.task_tracker.definition import (
    TaskTrackerAction,
    TaskTrackerObservation,
    TaskTrackerStatusType,
)
from openhands.tools.terminal.definition import TerminalAction


logger = get_logger(__name__)


def extract_action_locations(action: Action) -> list[ToolCallLocation] | None:
    """Extract file locations from an action if available.

    Returns a list of ToolCallLocation objects if the action contains location
    information (e.g., file paths, directories), otherwise returns None.

    Supports:
    - file_editor: path, view_range, insert_line
    - Other tools with 'path' or 'directory' attributes

    Args:
        action: Action to extract locations from

    Returns:
        List of ToolCallLocation objects or None
    """
    locations = []
    if isinstance(action, FileEditorAction):
        # Handle FileEditorAction specifically
        if action.path:
            location = ToolCallLocation(path=action.path)
            if action.view_range and len(action.view_range) > 0:
                location.line = action.view_range[0]
            elif action.insert_line is not None:
                location.line = action.insert_line
            locations.append(location)
    return locations if locations else None


def _event_visualize_to_plain(event: Event) -> str:
    """Convert Rich Text object to plain string.

    Args:
        text: Rich Text object or string

    Returns:
        Plain text string
    """
    text = event.visualize
    text = text.plain
    return str(text)


class EventSubscriber:
    """Subscriber for handling OpenHands events and converting them to ACP
    notifications.

    This class subscribes to events from an OpenHands conversation and converts
    them to ACP session update notifications that are streamed back to the client.
    """

    def __init__(self, session_id: str, conn: "AgentSideConnection"):
        """Initialize the event subscriber.

        Args:
            session_id: The ACP session ID
            conn: The ACP connection for sending notifications
        """
        self.session_id = session_id
        self.conn = conn

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
        elif isinstance(
            event, ObservationEvent | UserRejectObservation | AgentErrorEvent
        ):
            await self._handle_observation_event(event)
        elif isinstance(event, MessageEvent):
            await self._handle_message_event(event)
        elif isinstance(event, SystemPromptEvent):
            await self._handle_system_prompt_event(event)
        elif isinstance(event, PauseEvent):
            await self._handle_pause_event(event)
        elif isinstance(event, Condensation):
            await self._handle_condensation_event(event)
        elif isinstance(event, CondensationRequest):
            await self._handle_condensation_request_event(event)

    async def _handle_action_event(self, event: ActionEvent):
        """Handle ActionEvent: send thought as agent_message_chunk, then tool_call.

        Args:
            event: ActionEvent to process
        """
        try:
            # First, send thoughts/reasoning as agent_message_chunk if available
            thought_text = " ".join([t.text for t in event.thought])

            if event.reasoning_content and event.reasoning_content.strip():
                await self.conn.sessionUpdate(
                    SessionNotification(
                        sessionId=self.session_id,
                        update=AgentThoughtChunk(
                            sessionUpdate="agent_thought_chunk",
                            content=TextContentBlock(
                                type="text",
                                text="**Reasoning**:\n"
                                + event.reasoning_content.strip()
                                + "\n",
                            ),
                        ),
                    )
                )

            if thought_text.strip():
                await self.conn.sessionUpdate(
                    SessionNotification(
                        sessionId=self.session_id,
                        update=AgentThoughtChunk(
                            sessionUpdate="agent_thought_chunk",
                            content=TextContentBlock(
                                type="text",
                                text="\n**Thought**:\n" + thought_text.strip() + "\n",
                            ),
                        ),
                    )
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
                if action_viz.strip():
                    content = [
                        ContentToolCallContent(
                            type="content",
                            content=TextContentBlock(
                                type="text",
                                text=action_viz,
                            ),
                        )
                    ]

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
                    await self.conn.sessionUpdate(
                        SessionNotification(
                            sessionId=self.session_id,
                            update=AgentThoughtChunk(
                                sessionUpdate="agent_thought_chunk",
                                content=TextContentBlock(
                                    type="text",
                                    text=action_viz,
                                ),
                            ),
                        )
                    )
                    return
                elif isinstance(event.action, FinishAction):
                    await self.conn.sessionUpdate(
                        SessionNotification(
                            sessionId=self.session_id,
                            update=AgentMessageChunk(
                                sessionUpdate="agent_message_chunk",
                                content=TextContentBlock(
                                    type="text",
                                    text=action_viz,
                                ),
                            ),
                        )
                    )
                    return

            await self.conn.sessionUpdate(
                SessionNotification(
                    sessionId=self.session_id,
                    update=ToolCallStart(
                        sessionUpdate="tool_call",
                        toolCallId=event.tool_call_id,
                        title=title,
                        kind=tool_kind,
                        status="in_progress",
                        content=content,
                        locations=extract_action_locations(event.action)
                        if event.action
                        else None,
                        rawInput=event.action.model_dump() if event.action else None,
                    ),
                )
            )
        except Exception as e:
            logger.debug(f"Error processing ActionEvent: {e}", exc_info=True)

    async def _handle_observation_event(self, event: ObservationBaseEvent):
        """Handle observation events by sending tool_call_update notification.

        Handles special observation types (FileEditor, TaskTracker) with custom logic,
        and generic observations with visualization text.

        Args:
            event: ObservationEvent, UserRejectObservation, or AgentErrorEvent
        """
        try:
            content: ContentToolCallContent | None = None
            status: ToolCallStatus = "completed"
            if isinstance(event, ObservationEvent):
                if isinstance(event.observation, ThinkObservation | FinishObservation):
                    # Think and Finish observations are handled in action event
                    return
                # Special handling for TaskTrackerObservation
                elif isinstance(event.observation, TaskTrackerObservation):
                    observation = event.observation
                    # Convert TaskItems to PlanEntries
                    entries: list[PlanEntry] = []
                    for task in observation.task_list:
                        # Map status: todo→pending, in_progress→in_progress,
                        # done→completed
                        status_map: dict[TaskTrackerStatusType, PlanEntryStatus] = {
                            "todo": "pending",
                            "in_progress": "in_progress",
                            "done": "completed",
                        }
                        task_status = status_map.get(task.status, "pending")
                        task_content = task.title
                        # NOTE: we ignore notes for now to keep it concise
                        # if task.notes:
                        #     task_content += f"\n{task.notes}"
                        entries.append(
                            PlanEntry(
                                content=task_content,
                                status=task_status,
                                priority="medium",  # TaskItem doesn't have priority
                            )
                        )

                    # Send AgentPlanUpdate
                    await self.conn.sessionUpdate(
                        SessionNotification(
                            sessionId=self.session_id,
                            update=AgentPlanUpdate(
                                sessionUpdate="plan",
                                entries=entries,
                            ),
                        )
                    )
                else:
                    observation = event.observation
                    # Use ContentToolCallContent for view commands and other operations
                    viz_text = _event_visualize_to_plain(event)
                    if viz_text.strip():
                        content = ContentToolCallContent(
                            type="content",
                            content=TextContentBlock(
                                type="text",
                                text=viz_text,
                            ),
                        )
            else:
                # For UserRejectObservation or AgentErrorEvent
                status = "failed"
                viz_text = _event_visualize_to_plain(event)
                if viz_text.strip():
                    content = ContentToolCallContent(
                        type="content",
                        content=TextContentBlock(
                            type="text",
                            text=viz_text,
                        ),
                    )
            # Send tool_call_update for all observation types
            await self.conn.sessionUpdate(
                SessionNotification(
                    sessionId=self.session_id,
                    update=ToolCallProgress(
                        sessionUpdate="tool_call_update",
                        toolCallId=event.tool_call_id,
                        status=status,
                        content=[content] if content else None,
                        rawOutput=event.model_dump(),
                    ),
                )
            )
        except Exception as e:
            logger.debug(f"Error processing observation event: {e}", exc_info=True)

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
                await self.conn.sessionUpdate(
                    SessionNotification(
                        sessionId=self.session_id,
                        update=AgentMessageChunk(
                            sessionUpdate="agent_message_chunk",
                            content=TextContentBlock(
                                type="text",
                                text=viz_text,
                            ),
                        ),
                    )
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

            await self.conn.sessionUpdate(
                SessionNotification(
                    sessionId=self.session_id,
                    update=AgentThoughtChunk(
                        sessionUpdate="agent_thought_chunk",
                        content=TextContentBlock(
                            type="text",
                            text=viz_text,
                        ),
                    ),
                )
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

            await self.conn.sessionUpdate(
                SessionNotification(
                    sessionId=self.session_id,
                    update=AgentThoughtChunk(
                        sessionUpdate="agent_thought_chunk",
                        content=TextContentBlock(
                            type="text",
                            text=viz_text,
                        ),
                    ),
                )
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

            await self.conn.sessionUpdate(
                SessionNotification(
                    sessionId=self.session_id,
                    update=AgentThoughtChunk(
                        sessionUpdate="agent_thought_chunk",
                        content=TextContentBlock(
                            type="text",
                            text=viz_text,
                        ),
                    ),
                )
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

            await self.conn.sessionUpdate(
                SessionNotification(
                    sessionId=self.session_id,
                    update=AgentThoughtChunk(
                        sessionUpdate="agent_thought_chunk",
                        content=TextContentBlock(
                            type="text",
                            text=viz_text,
                        ),
                    ),
                )
            )
        except Exception as e:
            logger.debug(f"Error processing CondensationRequest: {e}", exc_info=True)
