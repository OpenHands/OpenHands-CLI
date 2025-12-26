"""
Utility functions for ACP implementation.

Refactor: split token streaming into a dedicated class.

- TokenStreamingHandler: owns `on_token` + all streaming helpers/state.
- EventSubscriber: keeps the event->ACP conversion logic (unchanged except it
  delegates `on_token` to TokenStreamingHandler).
"""

from __future__ import annotations

import asyncio

from acp import (
    Client,
    start_tool_call,
    update_agent_message_text,
    update_agent_thought_text,
    update_tool_call,
)
from acp.schema import (
    AgentMessageChunk,
    AgentPlanUpdate,
    AgentThoughtChunk,
    ToolCallProgress,
    ToolCallStart,
)

from openhands.sdk import BaseConversation, Event, get_logger
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    Condensation,
    CondensationRequest,
    ConversationStateUpdateEvent,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
    UserRejectObservation,
)
from openhands.sdk.llm.streaming import LLMStreamChunk
from openhands_cli.acp_impl.events.shared_event_handler import (
    REASONING_HEADER,
    SharedEventHandler,
)
from openhands_cli.acp_impl.events.tool_state import ToolCallState
from openhands_cli.acp_impl.events.utils import (
    format_content_blocks,
    get_metadata,
)


ACPUpdate = (
    AgentMessageChunk
    | AgentThoughtChunk
    | ToolCallStart
    | ToolCallProgress
    | AgentPlanUpdate
)


logger = get_logger(__name__)


class TokenBasedEventSubscriber:
    """Owns all token streaming logic + state (tool-call streaming included)."""

    def __init__(
        self,
        *,
        session_id: str,
        conn: Client,
        loop: asyncio.AbstractEventLoop,
        conversation: BaseConversation | None = None,
    ):
        self.session_id = session_id
        self.conn = conn
        self.loop = loop
        self.conversation = conversation

        # index -> ToolCallState
        self._streaming_tool_calls: dict[int, ToolCallState] = {}
        self.shared_events_handler = SharedEventHandler()

        # Header tracking for consistent formatting with non-streaming mode
        self._reasoning_header_emitted = False

    def reset_header_state(self) -> None:
        """Reset header tracking for a new LLM response.

        Called when starting a new streaming response to ensure headers
        are prepended to the first chunk of each section.
        """
        self._reasoning_header_emitted = False

    def _prune_tool_call_state(self, tool_call_id: str) -> None:
        """Remove any ToolCallState entries matching the given tool_call_id.

        This prevents memory accumulation over long sessions by cleaning up
        completed/failed tool call states.
        """
        indices_to_remove = [
            idx
            for idx, state in self._streaming_tool_calls.items()
            if state.tool_call_id == tool_call_id
        ]
        for idx in indices_to_remove:
            del self._streaming_tool_calls[idx]

    async def unstreamed_event_handler(self, event: Event):
        # Skip ConversationStateUpdateEvent (internal state management)
        if isinstance(event, ConversationStateUpdateEvent):
            return

        # Reset header state for next streaming response
        self.reset_header_state()

        if isinstance(event, ActionEvent):
            await self.shared_events_handler.handle_action_event(self, event)
        if isinstance(event, UserRejectObservation) or isinstance(
            event, AgentErrorEvent
        ):
            await self.shared_events_handler.handle_user_reject_or_agent_error(
                self, event
            )
            self._prune_tool_call_state(event.tool_call_id)
        elif isinstance(event, ObservationEvent):
            await self.shared_events_handler.handle_observation(self, event)
            self._prune_tool_call_state(event.tool_call_id)
        elif isinstance(event, SystemPromptEvent):
            await self.shared_events_handler.handle_system_prompt(self, event)
        elif isinstance(event, PauseEvent):
            await self.shared_events_handler.handle_pause(self, event)
        elif isinstance(event, Condensation):
            await self.shared_events_handler.handle_condensation(self, event)
        elif isinstance(event, CondensationRequest):
            await self.shared_events_handler.handle_condensation_request(self, event)

    def on_token(self, chunk: LLMStreamChunk) -> None:
        try:
            for choice in chunk.choices:
                delta = getattr(choice, "delta", None)
                if not delta:
                    continue

                choice_index = getattr(choice, "index", 0) or 0

                # Tool calls are already grouped by tool_call.index internally,
                # so we process them from all choices.
                tool_calls = getattr(delta, "tool_calls", None)
                if tool_calls:
                    for tool_call in tool_calls:
                        self._handle_tool_call_streaming(tool_call)

                # Only process content/reasoning from choice.index == 0.
                # We maintain single-stream state (_reasoning_header_emitted) that
                # cannot track per-choice headers. If a provider emits multiple
                # choices (n > 1) or out-of-order indices, processing all would
                # interleave content. Standard streaming uses n=1, so choice > 0
                # is rare; we ignore it to avoid corruption.
                if choice_index != 0:
                    continue

                reasoning = getattr(delta, "reasoning_content", None)
                content = getattr(delta, "content", None)

                if isinstance(reasoning, str) and reasoning:
                    # Prepend header on first reasoning chunk for consistency
                    # with non-streaming mode (EventSubscriber)
                    if not self._reasoning_header_emitted:
                        self._reasoning_header_emitted = True
                        reasoning = REASONING_HEADER + reasoning
                    self._schedule_update(update_agent_thought_text(reasoning))

                if isinstance(content, str) and content:
                    self._schedule_update(update_agent_message_text(content))

        except Exception as e:
            logger.warning("Error during token streaming: %s", e, exc_info=True)

    # -----------------------
    # internals
    # -----------------------

    def _schedule_update(self, update: ACPUpdate) -> None:
        """Schedule a session_update for an ACP update, thread-safe."""

        async def _send() -> None:
            await self.conn.session_update(
                session_id=self.session_id,
                update=update,
                field_meta=get_metadata(self.conversation),
            )

        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_send(), self.loop)
        else:
            self.loop.run_until_complete(_send())

    def _handle_tool_call_streaming(self, tool_call) -> None:
        if not tool_call:
            return

        index = getattr(tool_call, "index", 0) or 0
        tool_call_id = getattr(tool_call, "id", None)

        function = getattr(tool_call, "function", None)
        if not function:
            return

        name = getattr(function, "name", None)
        arguments_chunk = getattr(function, "arguments", None)

        if index not in self._streaming_tool_calls:
            if tool_call_id and name:
                state = ToolCallState(tool_call_id, name)
                self._streaming_tool_calls[index] = state

        elif tool_call_id and name:
            # Update existing state if we get new id/name (shouldn't happen often)
            existing_state = self._streaming_tool_calls[index]
            if existing_state.tool_call_id != tool_call_id:
                # New tool call at same index - replace state
                state = ToolCallState(tool_call_id, name)
                self._streaming_tool_calls[index] = state

        state = self._streaming_tool_calls.get(index)
        if not state:
            return

        # Append args first (before checking if we should start)
        if arguments_chunk:
            state.append_args(arguments_chunk)

        # Delay all tool call processing until we have a valid skeleton.
        # This prevents flickering from noisy models that emit a tool name
        # then hesitate or abandon the call.
        if not state.has_valid_skeleton:
            return

        # Handle think tool: extract thought and emit
        if state.is_think:
            thought_piece = state.extract_thought_piece()
            if thought_piece:
                self._schedule_update(update_agent_thought_text(thought_piece))
            return

        if not state.started:
            state.started = True
            tool_call_start = start_tool_call(
                tool_call_id=state.tool_call_id,
                title=state.title,
                kind=state.kind,
                status="in_progress",
                content=format_content_blocks(state.args),
            )
            self._schedule_update(tool_call_start)

        # Emit progress updates after start
        if state.started and arguments_chunk:
            self._schedule_update(
                update_tool_call(
                    tool_call_id=state.tool_call_id,
                    title=state.title,
                    kind=state.kind,
                    status="in_progress",
                    content=format_content_blocks(state.args),
                ),
            )
