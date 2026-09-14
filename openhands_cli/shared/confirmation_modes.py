"""Shared confirmation mode definitions.

This module provides a single source of truth for confirmation mode types and
descriptions used by both ACP and TUI interfaces.
"""

from typing import Literal, TypedDict


# Type alias for confirmation modes
ConfirmationMode = Literal["always-ask", "always-approve", "llm-approve"]


class ModeInfo(TypedDict):
    """TypedDict for confirmation mode information."""

    short: str
    long: str


# Confirmation mode descriptions
CONFIRMATION_MODES: dict[ConfirmationMode, ModeInfo] = {
    "always-ask": {
        "short": "Ask for permission before every action",
        "long": "Agent will ask for permission before executing every action.",
    },
    "always-approve": {
        "short": "Automatically approve all actions",
        "long": (
            "Agent will automatically approve all actions without asking. "
            "⚠️   Use with caution!"
        ),
    },
    "llm-approve": {
        "short": "Use LLM security analyzer to auto-approve safe actions",
        "long": (
            "Agent will use LLM security analyzer to automatically "
            "approve safe actions. You will only be asked for permission "
            "on potentially risky actions."
        ),
    },
}

# List of valid confirmation modes for validation
VALID_CONFIRMATION_MODES: list[ConfirmationMode] = list(CONFIRMATION_MODES.keys())
