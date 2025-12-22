"""Utility functions for ACP implementation."""

import asyncio

from acp import Client, RequestError
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

from openhands.sdk import Action, BaseConversation, get_logger
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
from openhands.sdk.llm.streaming import LLMStreamChunk
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

    def __init__(
        self,
        session_id: str,
        conn: "Client",
        conversation: BaseConversation | None = None,
        streaming_enabled: bool = False,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        """Initialize the event subscriber.

        Args:
            session_id: The ACP session ID
            conn: The ACP connection for sending notifications
            conversation: Optional conversation instance for accessing metrics
            streaming_enabled: Whether token streaming is enabled
            loop: Event loop for scheduling async operations (required for streaming)
        """
        self.session_id = session_id
        self.conn = conn
        self.conversation = conversation
        self.streaming_enabled = streaming_enabled
        self.loop = loop
        # Track streaming tool calls: index -> {tool_call_id, name, is_think}
        self._streaming_tool_calls: dict[int, dict[str, str | bool | None]] = {}

    def _format_status_line(self, usage, cost: float) -> str:
        """Format metrics as a status line string.

        Constructs a human-readable status line similar to the SDK's visualizer title,
        giving clients flexibility in how to display metrics.

        Args:
            usage: Token usage object with prompt_tokens, completion_tokens, etc.
            cost: Accumulated cost

        Returns:
            Formatted status line string
            (e.g., "↑ input 1.2K • cache hit 50.00% • ↓ output 500 • $ 0.0050")
        """

        # Helper function to abbreviate large numbers
        def abbr(n: int | float) -> str:
            n = int(n or 0)
            if n >= 1_000_000_000:
                val, suffix = n / 1_000_000_000, "B"
            elif n >= 1_000_000:
                val, suffix = n / 1_000_000, "M"
            elif n >= 1_000:
                val, suffix = n / 1_000, "K"
            else:
                return str(n)
            return f"{val:.2f}".rstrip("0").rstrip(".") + suffix

        input_tokens = abbr(usage.prompt_tokens or 0)
        output_tokens = abbr(usage.completion_tokens or 0)

        # Calculate cache hit rate (convert to int to handle mock objects safely)
        prompt = int(usage.prompt_tokens or 0)
        cache_read = int(usage.cache_read_tokens or 0)
        cache_rate = f"{(cache_read / prompt * 100):.2f}%" if prompt > 0 else "N/A"
        reasoning_tokens = int(usage.reasoning_tokens or 0)

        # Format cost (convert to float to handle mock objects safely)
        cost_val = float(cost or 0)
        cost_str = f"{cost_val:.4f}" if cost_val > 0 else "0.00"

        # Build status line
        parts: list[str] = []
        parts.append(f"↑ input {input_tokens}")
        parts.append(f"cache hit {cache_rate}")
        if reasoning_tokens > 0:
            parts.append(f"reasoning {abbr(reasoning_tokens)}")
        parts.append(f"↓ output {output_tokens}")
        parts.append(f"$ {cost_str}")

        return " • ".join(parts)

    def _get_metadata(self) -> dict[str, dict[str, int | float | str]] | None:
        """Get metrics data to include in the _meta field.

        Returns metrics data similar to how SDK's _format_metrics_subtitle works,
        extracting token usage and cost from conversation stats.

        Returns:
            Dictionary with metrics data or None if stats unavailable
        """
        if not self.conversation:
            return None

        stats = self.conversation.conversation_stats
        if not stats:
            return None

        combined_metrics = stats.get_combined_metrics()
        if not combined_metrics or not combined_metrics.accumulated_token_usage:
            return None

        usage = combined_metrics.accumulated_token_usage
        cost = combined_metrics.accumulated_cost or 0.0

        # Return structured metrics data including status_line
        return {
            "openhands.dev/metrics": {
                "input_tokens": usage.prompt_tokens or 0,
                "output_tokens": usage.completion_tokens or 0,
                "cache_read_tokens": usage.cache_read_tokens or 0,
                "reasoning_tokens": usage.reasoning_tokens or 0,
                "cost": cost,
                "status_line": self._format_status_line(usage, cost),
            }
        }

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
                    field_meta=self._get_metadata(),
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
                    field_meta=self._get_metadata(),
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
                    await self.conn.session_update(
                        session_id=self.session_id,
                        update=AgentThoughtChunk(
                            session_update="agent_thought_chunk",
                            content=TextContentBlock(
                                type="text",
                                text=action_viz,
                            ),
                        ),
                        field_meta=self._get_metadata(),
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
                        field_meta=self._get_metadata(),
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
                field_meta=self._get_metadata(),
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
                    await self.conn.session_update(
                        session_id=self.session_id,
                        update=AgentPlanUpdate(
                            session_update="plan",
                            entries=entries,
                        ),
                        field_meta=self._get_metadata(),
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
            await self.conn.session_update(
                session_id=self.session_id,
                update=ToolCallProgress(
                    session_update="tool_call_update",
                    tool_call_id=event.tool_call_id,
                    status=status,
                    content=[content] if content else None,
                    raw_output=event.model_dump(),
                ),
                field_meta=self._get_metadata(),
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
                # Skip sending complete assistant messages when streaming is enabled
                # since token callbacks are already streaming the content
                if self.streaming_enabled:
                    logger.debug(
                        "Skipping complete message event due to streaming being enabled"
                    )
                    return

                await self.conn.session_update(
                    session_id=self.session_id,
                    update=AgentMessageChunk(
                        session_update="agent_message_chunk",
                        content=TextContentBlock(
                            type="text",
                            text=viz_text,
                        ),
                    ),
                    field_meta=self._get_metadata(),
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
                field_meta=self._get_metadata(),
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
                field_meta=self._get_metadata(),
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
                field_meta=self._get_metadata(),
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
                field_meta=self._get_metadata(),
            )
        except Exception as e:
            logger.debug(f"Error processing CondensationRequest: {e}", exc_info=True)

    def on_token(self, chunk: LLMStreamChunk) -> None:
        """Handle streaming tokens and convert them to ACP AgentMessageChunk updates.

        This processes different types of streaming content including regular
        content, tool calls, and thinking blocks with dynamic boundary detection.

        Args:
            chunk: Streaming chunk from the LLM
        """
        # Note: Tool calls are handled by the event system through
        # ActionEvent -> ToolCallStart notifications, so we skip
        # streaming them here to avoid duplication

        if not self.loop:
            logger.warning("No event loop available for token streaming")
            return

        try:
            choices = chunk.choices
            for choice in choices:
                delta = choice.delta
                if not delta:
                    continue

                # Handle tool calls - specifically detect and stream think tool
                tool_calls = getattr(delta, "tool_calls", None)
                if tool_calls:
                    for tool_call in tool_calls:
                        self._handle_tool_call_streaming(tool_call)

                content_to_send = None
                is_reasoning_content = False

                # Handle reasoning content
                reasoning_content = getattr(delta, "reasoning_content", None)
                if isinstance(reasoning_content, str) and reasoning_content:
                    content_to_send = reasoning_content
                    is_reasoning_content = True

                # Handle regular content
                content = getattr(delta, "content", None)
                if isinstance(content, str) and content:
                    content_to_send = content

                if not content_to_send:
                    continue

                # Send content as AgentMessageChunk
                if self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self._send_streaming_chunk(
                            content_to_send, is_reasoning=is_reasoning_content
                        ),
                        self.loop,
                    )
                else:
                    # For testing or when loop is not running, run directly
                    self.loop.run_until_complete(
                        self._send_streaming_chunk(
                            content_to_send, is_reasoning=is_reasoning_content
                        )
                    )

        except Exception as e:
            raise RequestError.internal_error(
                {
                    "reason": "Error during token streaming",
                    "details": str(e),
                }
            )

    def _handle_tool_call_streaming(self, tool_call) -> None:
        """Handle streaming of tool calls.

        Sends ToolCallStart when a new tool call is detected, then streams arguments:
        - Think tool: streams via AgentThoughtChunk
        - Other tools: streams via ToolCallProgress

        Args:
            tool_call: Tool call object from the LLM streaming delta
        """
        if not tool_call:
            return

        index = getattr(tool_call, "index", 0) or 0
        tool_call_id = getattr(tool_call, "id", None)
        function = getattr(tool_call, "function", None)
        if not function:
            return

        name = getattr(function, "name", None)
        arguments = getattr(function, "arguments", None)

        # Register new tool call when we see the id and/or name
        if index not in self._streaming_tool_calls:
            if tool_call_id or name:
                is_think = name == "think" if name else False
                self._streaming_tool_calls[index] = {
                    "tool_call_id": tool_call_id,
                    "name": name,
                    "is_think": is_think,
                    "started": False,  # Track if ToolCallStart has been sent
                }
        else:
            # Update existing tool call info if we get new data
            if tool_call_id:
                self._streaming_tool_calls[index]["tool_call_id"] = tool_call_id
            if name:
                self._streaming_tool_calls[index]["name"] = name
                self._streaming_tool_calls[index]["is_think"] = name == "think"

        # Send ToolCallStart for non-think tools when we have enough info
        tool_info = self._streaming_tool_calls.get(index, {})
        stored_tool_call_id = tool_info.get("tool_call_id")
        stored_name = tool_info.get("name")
        is_think = tool_info.get("is_think", False)
        has_started = tool_info.get("started", False)

        # Send ToolCallStart when we have tool_call_id and name, but haven't started yet
        if (
            stored_tool_call_id
            and stored_name
            and not has_started
            and not is_think
            and isinstance(stored_tool_call_id, str)
            and isinstance(stored_name, str)
        ):
            self._streaming_tool_calls[index]["started"] = True
            self._schedule_async(
                self._send_tool_call_start(stored_tool_call_id, stored_name)
            )

        # Stream arguments if we have them and the tool is registered
        if index in self._streaming_tool_calls and arguments:
            if is_think:
                # Stream think tool arguments as AgentThoughtChunk
                thought_content = self._extract_thought_from_args(arguments)
                if thought_content:
                    self._schedule_async(
                        self._send_streaming_chunk(thought_content, is_reasoning=True)
                    )
            elif stored_tool_call_id and isinstance(stored_tool_call_id, str):
                # Stream other tools via ToolCallProgress
                self._schedule_async(
                    self._send_tool_call_progress(stored_tool_call_id, arguments)
                )

    def _schedule_async(self, coro) -> None:
        """Schedule an async coroutine to run on the event loop.

        Args:
            coro: Coroutine to schedule
        """
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self.loop)
        elif self.loop:
            self.loop.run_until_complete(coro)

    def _extract_thought_from_args(self, arguments: str) -> str | None:
        """Extract thought content from streaming tool call arguments.

        Filters out JSON syntax to extract just the thought text.

        Args:
            arguments: Incremental arguments string from tool call

        Returns:
            Extracted thought text or None if only JSON syntax
        """
        if not arguments:
            return None

        # Filter out JSON syntax characters that shouldn't be displayed
        # These are the structural parts of {"thought": "..."}
        json_syntax = {"{", "}", '"', ":", "thought", "\\"}

        # Check if this is purely JSON syntax
        stripped = arguments.strip()
        if stripped in json_syntax:
            return None
        if stripped == '{"thought':
            return None
        if stripped == '": "':
            return None
        if stripped == '"}':
            return None

        # Return the content that is part of the actual thought text
        return arguments

    def _get_tool_kind_from_name(self, tool_name: str) -> ToolKind:
        """Map tool name to ToolKind.

        Args:
            tool_name: The name of the tool

        Returns:
            The appropriate ToolKind for the tool
        """
        tool_kind_mapping: dict[str, ToolKind] = {
            "terminal": "execute",
            "browser_use": "fetch",
            "browser": "fetch",
            "browser_navigate": "fetch",
            "browser_click": "fetch",
            "browser_type": "fetch",
            "browser_scroll": "fetch",
            "browser_get_state": "fetch",
            "browser_get_content": "fetch",
            "browser_go_back": "fetch",
            "browser_list_tabs": "fetch",
            "browser_switch_tab": "fetch",
            "browser_close_tab": "fetch",
            "file_editor": "edit",
            "think": "think",
            "finish": "other",
            "task_tracker": "other",
        }
        return tool_kind_mapping.get(tool_name, "other")

    async def _send_tool_call_start(self, tool_call_id: str, tool_name: str) -> None:
        """Send ToolCallStart notification when a tool call begins streaming.

        Args:
            tool_call_id: The ID of the tool call
            tool_name: The name of the tool being called
        """
        try:
            tool_kind = self._get_tool_kind_from_name(tool_name)
            await self.conn.session_update(
                session_id=self.session_id,
                update=ToolCallStart(
                    session_update="tool_call",
                    tool_call_id=tool_call_id,
                    title=tool_name,
                    kind=tool_kind,
                    status="in_progress",
                ),
            )
        except Exception as e:
            logger.debug(f"Error sending tool call start: {e}", exc_info=True)

    async def _send_tool_call_progress(self, tool_call_id: str, arguments: str) -> None:
        """Send tool call progress update via ToolCallProgress.

        Args:
            tool_call_id: The ID of the tool call
            arguments: The streaming arguments content
        """
        try:
            await self.conn.session_update(
                session_id=self.session_id,
                update=ToolCallProgress(
                    session_update="tool_call_update",
                    tool_call_id=tool_call_id,
                    content=[
                        ContentToolCallContent(
                            type="content",
                            content=TextContentBlock(
                                type="text",
                                text=arguments,
                            ),
                        )
                    ],
                ),
            )
        except Exception as e:
            logger.debug(f"Error sending tool call progress: {e}", exc_info=True)

    async def _send_streaming_chunk(self, content: str, is_reasoning: bool = False):
        """Send a streaming chunk as an ACP update.

        Args:
            content: The content to send
            is_reasoning: Whether this is reasoning content (sent as AgentThoughtChunk)
        """
        try:
            if is_reasoning:
                # Send reasoning content as AgentThoughtChunk
                await self.conn.session_update(
                    session_id=self.session_id,
                    update=AgentThoughtChunk(
                        session_update="agent_thought_chunk",
                        content=TextContentBlock(
                            type="text",
                            text=content,
                        ),
                    ),
                )
            else:
                # Send regular content as AgentMessageChunk
                await self.conn.session_update(
                    session_id=self.session_id,
                    update=AgentMessageChunk(
                        session_update="agent_message_chunk",
                        content=TextContentBlock(
                            type="text",
                            text=content,
                        ),
                    ),
                )
        except Exception as e:
            logger.debug(f"Error sending streaming chunk: {e}", exc_info=True)
