"""Shared tool kind mapping for ACP protocol.

Provides a mapping from tool names to ACP ToolKind values, used by both
the ACP event utilities and the tool call state machine.
"""

from acp.schema import ToolKind


TOOL_KIND_MAPPING: dict[str, ToolKind] = {
    "terminal": "execute",
    "browser_use": "fetch",
    "browser": "fetch",
}
