"""Compatibility support for legacy DelegateTool conversations."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from openhands.sdk.tool import ToolAnnotations, ToolDefinition, register_tool
from openhands.sdk.tool.registry import list_registered_tools
from openhands.tools.delegate.definition import DelegateAction, DelegateObservation
from openhands.tools.delegate.impl import DelegateExecutor


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState


LEGACY_DELEGATE_TOOL_NAME = "delegate"

_DELEGATE_TOOL_DESCRIPTION = """
Delegate work to sub-agents. Use `spawn` first to create one or more named
sub-agents, then use `delegate` to assign tasks to them and wait for results.
""".strip()


class DelegateTool(ToolDefinition[DelegateAction, DelegateObservation]):
    """ToolDefinition wrapper for the removed DelegateTool public class."""

    name = LEGACY_DELEGATE_TOOL_NAME

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",  # noqa: ARG003
    ) -> Sequence[ToolDefinition]:
        return [
            cls(
                description=_DELEGATE_TOOL_DESCRIPTION,
                action_type=DelegateAction,
                observation_type=DelegateObservation,
                annotations=ToolAnnotations(
                    title=LEGACY_DELEGATE_TOOL_NAME,
                    readOnlyHint=False,
                    destructiveHint=True,
                    idempotentHint=False,
                    openWorldHint=True,
                ),
                executor=DelegateExecutor(),
            )
        ]


if LEGACY_DELEGATE_TOOL_NAME not in list_registered_tools():
    register_tool(LEGACY_DELEGATE_TOOL_NAME, DelegateTool)
