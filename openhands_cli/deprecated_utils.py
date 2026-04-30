"""Deprecated utility functions kept for backward compatibility.

These functions support legacy conversation formats (e.g., DelegateTool)
and will be removed once all persisted conversations have migrated.
"""

import json
from contextlib import suppress
from pathlib import Path

from openhands.tools.delegate import DelegateTool
from openhands_cli.locations import get_conversations_dir


def conversation_has_delegate_tool(conversation_id: str) -> bool:
    """Check if a conversation was configured with DelegateTool.

    Reads only the SystemPromptEvent (event-00000-*) and checks its ``tools``
    list for a tool titled "delegate", rather than scanning every event file.

    Args:
        conversation_id: The conversation ID to check

    Returns:
        True if the conversation's SystemPromptEvent lists DelegateTool,
        False otherwise
    """
    conversations_dir = get_conversations_dir()
    # Normalize: directory names use hex (no dashes), but callers may pass
    # str(UUID) which includes dashes.
    normalized_id = conversation_id.replace("-", "")
    events_dir = Path(conversations_dir) / normalized_id / "events"

    if not events_dir.exists():
        return False

    system_prompt_files = sorted(events_dir.glob("event-00000-*.json"))
    if not system_prompt_files:
        return False

    with suppress(OSError, json.JSONDecodeError):
        with open(system_prompt_files[0], encoding="utf-8") as f:
            event_data = json.load(f)
        for tool in event_data.get("tools", []):
            if isinstance(tool, dict) and tool.get("title") == DelegateTool.name:
                return True

    return False
