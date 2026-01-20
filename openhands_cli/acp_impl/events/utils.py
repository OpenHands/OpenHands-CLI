from acp import text_block, tool_content
from acp.schema import (
    ContentToolCallContent,
    FileEditToolCallContent,
    TerminalToolCallContent,
    ToolCallLocation,
    ToolKind,
)

from openhands.sdk import Action, BaseConversation
from openhands.tools.delegate.definition import DelegateAction
from openhands.tools.file_editor.definition import (
    FileEditorAction,
)
from openhands.tools.terminal import TerminalAction
from openhands_cli.shared.delegate_formatter import format_delegate_title
from openhands_cli.utils import abbreviate_number, format_cost


# Shared mapping from tool names to ACP ToolKind values
TOOL_KIND_MAPPING: dict[str, ToolKind] = {
    "terminal": "execute",
    "browser_use": "fetch",
    "browser": "fetch",
}


def _format_status_line(usage, cost: float) -> str:
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
    input_tokens = abbreviate_number(usage.prompt_tokens or 0)
    output_tokens = abbreviate_number(usage.completion_tokens or 0)

    # Calculate cache hit rate (convert to int to handle mock objects safely)
    prompt = int(usage.prompt_tokens or 0)
    cache_read = int(usage.cache_read_tokens or 0)
    cache_rate = f"{(cache_read / prompt * 100):.2f}%" if prompt > 0 else "N/A"
    reasoning_tokens = int(usage.reasoning_tokens or 0)

    # Build status line
    parts: list[str] = []
    parts.append(f"↑ input {input_tokens}")
    parts.append(f"cache hit {cache_rate}")
    if reasoning_tokens > 0:
        parts.append(f"reasoning {abbreviate_number(reasoning_tokens)}")
    parts.append(f"↓ output {output_tokens}")
    parts.append(f"$ {format_cost(float(cost or 0))}")

    return " • ".join(parts)


def get_metadata(
    conversation: BaseConversation | None,
) -> dict[str, dict[str, int | float | str]] | None:
    """Get metrics data to include in the _meta field.

    Returns metrics data similar to how SDK's _format_metrics_subtitle works,
    extracting token usage and cost from conversation stats.

    Returns:
        Dictionary with metrics data or None if stats unavailable
    """
    if not conversation:
        return None

    stats = conversation.conversation_stats
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
            "status_line": _format_status_line(usage, cost),
        }
    }


ToolCallContent = (
    ContentToolCallContent | FileEditToolCallContent | TerminalToolCallContent
)


def format_content_blocks(text: str | None) -> list[ToolCallContent] | None:
    if not text or not text.strip():
        return None
    return [
        tool_content(
            block=text_block(text=text),
        )
    ]


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


def get_tool_kind(tool_name: str, *, action: Action | None = None) -> ToolKind:
    """Get tool kind from tool name and optional complete action.

    For streaming tool calls, use ToolCallState.kind instead.
    """
    if tool_name == "think":
        return "think"

    if tool_name.startswith("browser"):
        return "fetch"

    if isinstance(action, FileEditorAction):
        if action.command == "view":
            return "read"
        return "edit"

    if isinstance(action, DelegateAction):
        return "other"

    return TOOL_KIND_MAPPING.get(tool_name, "other")


def get_tool_title(
    tool_name: str, *, action: Action | None = None, summary: str | None = None
) -> str:
    """Get tool title from tool name, action, and optional LLM-generated summary.

    When a summary is provided, it is used as the primary title with action
    details appended for context. This matches the TUI behavior.

    For streaming tool calls, use ToolCallState.title instead.

    Args:
        tool_name: The name of the tool being called
        action: Optional complete action object for extracting details
        summary: Optional LLM-generated summary describing the action's purpose

    Returns:
        A descriptive title for the tool call
    """
    # Clean up summary if provided
    clean_summary = summary.strip().replace("\n", " ") if summary else ""

    if isinstance(action, FileEditorAction):
        op = "Reading" if action.command == "view" else "Editing"
        path = action.path or ""
        if clean_summary:
            return f"{clean_summary}: {op} {path}"
        return f"{op} {path}"

    if isinstance(action, TerminalAction):
        cmd = action.command.strip().replace("\n", " ") if action.command else ""
        if clean_summary:
            return f"{clean_summary}: $ {cmd}"
        return f"$ {cmd}" if cmd else tool_name

    # For other actions, use summary if available
    if clean_summary:
        return clean_summary

    if isinstance(action, DelegateAction):
        return format_delegate_title(action.command, ids=action.ids, tasks=action.tasks)

    return ""
