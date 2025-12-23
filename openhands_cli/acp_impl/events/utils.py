from acp.schema import (
    ContentToolCallContent,
    FileEditToolCallContent,
    TerminalToolCallContent,
    TextContentBlock,
    ToolCallLocation,
)

from openhands.sdk import Action, BaseConversation
from openhands.tools.file_editor.definition import (
    FileEditorAction,
)


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
        ContentToolCallContent(
            type="content",
            content=TextContentBlock(type="text", text=text),
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
