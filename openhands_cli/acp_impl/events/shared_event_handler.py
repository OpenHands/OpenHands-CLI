from __future__ import annotations

from typing import Protocol

from acp import (
    Client,
    start_tool_call,
    update_agent_message_text,
    update_agent_thought_text,
)
from acp.schema import (
    AgentPlanUpdate,
    PlanEntry,
    PlanEntryStatus,
    ToolCallProgress,
    ToolCallStatus,
)

from openhands.sdk import BaseConversation, get_logger
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    Condensation,
    CondensationRequest,
    Event,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
    UserRejectObservation,
)
from openhands.sdk.tool.builtins.finish import FinishAction, FinishObservation
from openhands.sdk.tool.builtins.think import ThinkAction, ThinkObservation
from openhands.tools.task_tracker.definition import (
    TaskTrackerObservation,
    TaskTrackerStatusType,
)
from openhands_cli.acp_impl.events.utils import (
    extract_action_locations,
    format_content_blocks,
    get_metadata,
    get_tool_kind,
    get_tool_title,
)


logger = get_logger(__name__)

# Formatting constants for consistent headers across streaming and non-streaming modes
REASONING_HEADER = "**Reasoning**:\n"
THOUGHT_HEADER = "\n**Thought**:\n"


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
        await ctx.conn.session_update(
            session_id=ctx.session_id,
            update=update_agent_thought_text(text=text),
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
        await self.send_thought(ctx, str(event.visualize.plain))

    async def handle_condensation(self, ctx: _ACPContext, event: Condensation) -> None:
        await self.send_thought(ctx, _event_visualize_to_plain(event))

    async def handle_condensation_request(
        self, ctx: _ACPContext, event: CondensationRequest
    ) -> None:
        await self.send_thought(ctx, _event_visualize_to_plain(event))

    async def handle_user_reject_or_agent_error(
        self, ctx: _ACPContext, event: UserRejectObservation | AgentErrorEvent
    ) -> None:
        await self.send_tool_progress(
            ctx,
            tool_call_id=event.tool_call_id,
            status="failed",
            text=_event_visualize_to_plain(event),
            raw_output=event.model_dump(),
        )

    async def handle_observation(
        self, ctx: _ACPContext, event: ObservationEvent
    ) -> None:
        obs = event.observation
        if isinstance(obs, ThinkObservation) or isinstance(obs, FinishObservation):
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

    async def handle_action_event(self, ctx: _ACPContext, event: ActionEvent):
        content = None
        tool_kind = get_tool_kind(tool_name=event.tool_name, action=event.action)
        # Use LLM-generated summary for the title when available
        summary = str(event.summary) if event.summary else None
        title = get_tool_title(
            tool_name=event.tool_name, action=event.action, summary=summary
        )
        if event.action:
            action_viz = _event_visualize_to_plain(event)
            content = format_content_blocks(action_viz)

            if isinstance(event.action, ThinkAction):
                await ctx.conn.session_update(
                    session_id=ctx.session_id,
                    update=update_agent_thought_text(action_viz),
                    field_meta=self._meta(ctx),
                )
                return
            elif isinstance(event.action, FinishAction):
                await ctx.conn.session_update(
                    session_id=ctx.session_id,
                    update=update_agent_message_text(action_viz),
                    field_meta=self._meta(ctx),
                )
                return

        await ctx.conn.session_update(
            session_id=ctx.session_id,
            update=start_tool_call(
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
            field_meta=self._meta(ctx),
        )
