from __future__ import annotations

import asyncio
from typing import Protocol

from acp import Client
from acp.schema import (
    AgentMessageChunk,
    AgentPlanUpdate,
    AgentThoughtChunk,
    ContentToolCallContent,
    PlanEntry,
    PlanEntryStatus,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStatus,
)

from openhands.sdk import BaseConversation, get_logger
from openhands.sdk.event import (
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
from openhands.sdk.tool.builtins.finish import FinishObservation
from openhands.sdk.tool.builtins.think import ThinkObservation
from openhands.tools.task_tracker.definition import (
    TaskTrackerObservation,
    TaskTrackerStatusType,
)
from openhands_cli.acp_impl.events.utils import format_content_blocks, get_metadata

logger = get_logger(__name__)


def _event_visualize_to_plain(event: Event) -> str:
    return str(event.visualize.plain)


class _ACPContext(Protocol):
    session_id: str
    conn: Client
    conversation: BaseConversation | None


class SharedEventHandler:
    """Shared event-to-ACP behavior used by multiple subscribers."""

    def _meta(self, ctx: _ACPContext):
        return get_metadata(ctx.conversation)

    async def send_thought(self, ctx: _ACPContext, text: str) -> None:
        if not text.strip():
            return
        await ctx.conn.session_update(
            session_id=ctx.session_id,
            update=AgentThoughtChunk(
                session_update="agent_thought_chunk",
                content=TextContentBlock(type="text", text=text),
            ),
            field_meta=self._meta(ctx),
        )

    async def send_message(self, ctx: _ACPContext, text: str) -> None:
        if not text.strip():
            return
        await ctx.conn.session_update(
            session_id=ctx.session_id,
            update=AgentMessageChunk(
                session_update="agent_message_chunk",
                content=TextContentBlock(type="text", text=text),
            ),
            field_meta=self._meta(ctx),
        )

    async def send_tool_progress(
        self,
        ctx: _ACPContext,
        *,
        tool_call_id: str,
        status: ToolCallStatus,
        text: str | None,
        raw_output: dict,
    ) -> None:
        content = None
        
        await ctx.conn.session_update(
            session_id=ctx.session_id,
            update=ToolCallProgress(
                session_update="tool_call_update",
                tool_call_id=tool_call_id,
                status=status,
                content=format_content_blocks(text),
                raw_output=raw_output,
            ),
            field_meta=self._meta(ctx),
        )

    # -----------------------
    # Shared handlers
    # -----------------------

    async def handle_pause(self, ctx: _ACPContext, event: PauseEvent) -> None:
        await self.send_thought(ctx, _event_visualize_to_plain(event))

    async def handle_system_prompt(
        self, ctx: _ACPContext, event: SystemPromptEvent
    ) -> None:
        await self.send_thought(ctx, _event_visualize_to_plain(event))

    async def handle_condensation(self, ctx: _ACPContext, event: Condensation) -> None:
        await self.send_thought(ctx, _event_visualize_to_plain(event))

    async def handle_condensation_request(
        self, ctx: _ACPContext, event: CondensationRequest
    ) -> None:
        await self.send_thought(ctx, _event_visualize_to_plain(event))

    async def handle_user_reject(
        self, ctx: _ACPContext, event: UserRejectObservation
    ) -> None:
        await self.send_tool_progress(
            ctx,
            tool_call_id=event.tool_call_id,
            status="failed",
            text=_event_visualize_to_plain(event),
            raw_output=event.model_dump(),
        )

    async def handle_agent_error(
        self, ctx: _ACPContext, event: AgentErrorEvent
    ) -> None:
        await self.send_tool_progress(
            ctx,
            tool_call_id=event.tool_call_id,
            status="failed",
            text=_event_visualize_to_plain(event),
            raw_output=event.model_dump(),
        )

    async def handle_observation(self, ctx: _ACPContext, event: ObservationEvent) -> None:
        obs = event.observation
        if isinstance(obs, (ThinkObservation, FinishObservation)):
            return

        if isinstance(obs, TaskTrackerObservation):
            status_map: dict[TaskTrackerStatusType, PlanEntryStatus] = {
                "todo": "pending",
                "in_progress": "in_progress",
                "done": "completed",
            }
            entries: list[PlanEntry] = [
                PlanEntry(
                    content=task.title,
                    status=status_map.get(task.status, "pending"),
                    priority="medium",
                )
                for task in obs.task_list
            ]
            await ctx.conn.session_update(
                session_id=ctx.session_id,
                update=AgentPlanUpdate(session_update="plan", entries=entries),
                field_meta=self._meta(ctx),
            )
            return

        await self.send_tool_progress(
            ctx,
            tool_call_id=event.tool_call_id,
            status="completed",
            text=_event_visualize_to_plain(event),
            raw_output=event.model_dump(),
        )

    async def handle_message(
        self,
        ctx: _ACPContext,
        event: MessageEvent,
        *,
        streaming_enabled: bool,
    ) -> None:
        viz = _event_visualize_to_plain(event)
        if not viz.strip():
            return

        if event.llm_message.role == "user":
            # Keep your existing policy: don't re-emit user messages.
            return

        if streaming_enabled:
            logger.debug("Skipping complete message event due to streaming being enabled")
            return

        await self.send_message(ctx, viz)

