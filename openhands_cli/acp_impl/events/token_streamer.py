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
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
    ToolKind,
)
from openhands.sdk import get_logger
from openhands.sdk.llm.streaming import LLMStreamChunk
from openhands_cli.acp_impl.events.tool_state import ToolCallState

logger = get_logger(__name__)


class TokenBasedEventSubscriber:
    """Owns all token streaming logic + state (tool-call streaming included)."""

    def __init__(self, *, session_id: str, conn: Client, loop: asyncio.AbstractEventLoop):
        self.session_id = session_id
        self.conn = conn
        self.loop = loop

        # index -> ToolCallState
        self._streaming_tool_calls: dict[int, ToolCallState] = {}

    def on_token(self, chunk: LLMStreamChunk) -> None:
        if not self.loop:
            logger.warning("No event loop available for token streaming")
            return

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
                    self._schedule(self._send_streaming_chunk(reasoning, is_reasoning=True))

                if isinstance(content, str) and content:
                    self._schedule(self._send_streaming_chunk(content, is_reasoning=False))

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

        if not tool_call_id or not name:
            return

        state = self._streaming_tool_calls.get(index)
        if state is None or state.tool_call_id != tool_call_id:
            state = ToolCallState(tool_call_id, name, is_think=(name == "think"))
            self._streaming_tool_calls[index] = state

        # Start non-think tool calls once
        if not state.started and not state.is_think:
            state.started = True
            self._schedule(self._send_tool_call_start(state))

        # Stream args
        if not arguments:
            return

        state.append_args(arguments)

        if state.is_think:
            thought_piece = self._extract_thought_piece(arguments)
            if thought_piece:
                self._schedule(self._send_streaming_chunk(thought_piece, is_reasoning=True))
            return

        if state.started:
            self._schedule(self._send_tool_call_progress(state))

    def _extract_thought_piece(self, arguments: str) -> str | None:
        """Best-effort filter to avoid spamming JSON structure for think tool."""
        if not arguments:
            return None

        stripped = arguments.strip()
        # common incremental JSON fragments
        if stripped in {"{", "}", '"', ":", "thought", "\\"}:
            return None
        if stripped in {'{"thought', '": "', '"}', '"}'}:
            return None
        return arguments

    def _get_tool_kind(self, tool_name: str) -> ToolKind:
        match tool_name:
            case "terminal":
                return "execute"
            case "file_editor":
                return "edit"
            case "think":
                return "think"
            case "task_tracker" | "finish":
                return "search"  # pick something acceptable for ACP schema
            case _ if tool_name.startswith("browser"):
                return "search"  # or "read" depending on how your UI treats it
            case _:
                return "search"

    async def _send_tool_call_start(self, state: ToolCallState) -> None:
        try:
            await self.conn.session_update(
                session_id=self.session_id,
                update=ToolCallStart(
                    session_update="tool_call",
                    tool_call_id=state.tool_call_id,
                    title=state.title,
                    kind=self._get_tool_kind(state.tool_name),
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

