"""
Utility functions for ACP implementation.

Refactor: split token streaming into a dedicated class.

- TokenStreamingHandler: owns `on_token` + all streaming helpers/state.
- EventSubscriber: keeps the event->ACP conversion logic (unchanged except it
  delegates `on_token` to TokenStreamingHandler).
"""

from __future__ import annotations

import asyncio

from acp import Client, RequestError
from acp.schema import (
    AgentMessageChunk,
    AgentThoughtChunk,
    ContentToolCallContent,
    FileEditToolCallContent,
    TerminalToolCallContent,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
    ToolKind,
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
from openhands_cli.acp_impl.events.tool_state import ToolCallState
from openhands_cli.acp_impl.events.utils import extract_action_locations, get_metadata


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

    async def unstreamed_event_handler(self, event: Event):
        # Skip ConversationStateUpdateEvent (internal state management)
        if isinstance(event, ConversationStateUpdateEvent):
            return

        if isinstance(event, ActionEvent):
            await self._handle_action_event(event)
        if isinstance(event, UserRejectObservation) or isinstance(
            event, AgentErrorEvent
        ):
            await self.shared_events_handler.handle_user_reject_or_agent_error(
                self, event
            )
        elif isinstance(event, ObservationEvent):
            await self.shared_events_handler.handle_observation(self, event)
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

                # Tool calls (stream only: think args and dynamic titles/progress)
                tool_calls = getattr(delta, "tool_calls", None)
                if tool_calls:
                    for tool_call in tool_calls:
                        self._handle_tool_call_streaming(tool_call)

                # Reasoning + content streaming
                reasoning = getattr(delta, "reasoning_content", None)
                content = getattr(delta, "content", None)

                if isinstance(reasoning, str) and reasoning:
                    self._schedule(
                        self._send_streaming_chunk(reasoning, is_reasoning=True)
                    )

                if isinstance(content, str) and content:
                    self._schedule(
                        self._send_streaming_chunk(content, is_reasoning=False)
                    )

        except Exception as e:
            # NOTE: this surfaces as an ACP internal error (matches your ask)
            raise RequestError.internal_error(
                {"reason": "Error during token streaming", "details": str(e)}
            )

    # -----------------------
    # internals
    # -----------------------

    def _schedule(self, coro) -> None:
        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self.loop)
        else:
            self.loop.run_until_complete(coro)

    def _handle_tool_call_streaming(self, tool_call) -> None:
        if not tool_call:
            return

        index = getattr(tool_call, "index", 0) or 0
        tool_call_id = getattr(tool_call, "id", None)

        function = getattr(tool_call, "function", None)
        if not function:
            return

        name = getattr(function, "name", None)
        arguments = getattr(function, "arguments", None)

        # if not tool_call_id or not name:
        #     return

        if index not in self._streaming_tool_calls:
            if tool_call_id and name:
                state = ToolCallState(tool_call_id, name)
                self._streaming_tool_calls[index] = state
                self._last_tool_call_state = state

        elif tool_call_id and name:
            # Update existing state if we get new id/name (shouldn't happen often)
            existing_state = self._streaming_tool_calls[index]
            if existing_state.tool_call_id != tool_call_id:
                # New tool call at same index - replace state
                state = ToolCallState(tool_call_id, name)
                self._streaming_tool_calls[index] = state
                self._last_tool_call_state = state

        state = self._streaming_tool_calls.get(index)
        if not state:
            return

        # Start non-think tool calls once
        if not state.started and not state.is_think:
            state.started = True
            self._schedule(self._send_tool_call_start(state))

        # Stream args
        if not arguments:
            return

        state.append_args(arguments)

        thought_piece = state.extract_thought_piece(arguments)
        if thought_piece:
            self._schedule(self._send_streaming_chunk(thought_piece, is_reasoning=True))
            return

        if state.started:
            self._schedule(self._send_tool_call_progress(state))

    def _get_tool_kind(
        self, tool_name: str, state: ToolCallState | None = None
    ) -> ToolKind:
        """
        Keep tool->kind mapping consistent with _handle_action_event.
        If we have streaming args (state), we can refine file_editor view->read.
        """
        # Same mapping as _handle_action_event
        tool_kind_mapping: dict[str, ToolKind] = {
            "terminal": "execute",
            "browser_use": "fetch",
            "browser": "fetch",
        }

        if tool_name == "think":
            return "think"

        if tool_name == "file_editor" and state is not None:
            try:
                import json

                args = json.loads(state.lexer.complete_json())
                if isinstance(args, dict) and args.get("command") == "view":
                    return "read"
                return "edit"
            except Exception:
                # If args are incomplete, default to edit (safe + consistent)
                return "edit"

        if tool_name.startswith("browser"):
            # Covers browser*, browser_use*, etc.
            return "fetch"

        return tool_kind_mapping.get(tool_name, "other")

    async def _send_tool_call_start(self, state: ToolCallState) -> None:
        try:
            await self.conn.session_update(
                session_id=self.session_id,
                update=ToolCallStart(
                    session_update="tool_call",
                    tool_call_id=state.tool_call_id,
                    title=state.title,
                    kind=self._get_tool_kind(state.tool_name, state),
                    status="in_progress",
                    content=(
                        [
                            ContentToolCallContent(
                                type="content",
                                content=TextContentBlock(type="text", text=state.args),
                            )
                        ]
                        if state.args
                        else None
                    ),
                ),
            )
        except Exception as e:
            logger.debug(f"Error sending tool call start: {e}", exc_info=True)

    async def _send_tool_call_progress(self, state: ToolCallState) -> None:
        try:
            await self.conn.session_update(
                session_id=self.session_id,
                update=ToolCallProgress(
                    session_update="tool_call_update",
                    tool_call_id=state.tool_call_id,
                    title=state.title,
                    kind=self._get_tool_kind(state.tool_name, state),
                    status="in_progress",
                    content=[
                        ContentToolCallContent(
                            type="content",
                            content=TextContentBlock(type="text", text=state.args),
                        )
                    ],
                ),
            )
        except Exception as e:
            logger.debug(f"Error sending tool call progress: {e}", exc_info=True)

    async def _send_streaming_chunk(self, content: str, *, is_reasoning: bool) -> None:
        try:
            if is_reasoning:
                await self.conn.session_update(
                    session_id=self.session_id,
                    update=AgentThoughtChunk(
                        session_update="agent_thought_chunk",
                        content=TextContentBlock(type="text", text=content),
                    ),
                )
            else:
                await self.conn.session_update(
                    session_id=self.session_id,
                    update=AgentMessageChunk(
                        session_update="agent_message_chunk",
                        content=TextContentBlock(type="text", text=content),
                    ),
                )
        except Exception as e:
            logger.debug(f"Error sending streaming chunk: {e}", exc_info=True)

    async def _handle_action_event(self, event: ActionEvent):
        """Handle ActionEvent: send thought as agent_message_chunk, then tool_call.

        Args:
            event: ActionEvent to process
        """
        try:
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
                update=ToolCallProgress(
                    session_update="tool_call_update",
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
