"""Slash command handlers for ACP agent."""

import logging
from typing import Literal

from acp.schema import AvailableCommand
from openhands.sdk import BaseConversation
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands_cli.acp_impl.slash_commands import SlashCommandRegistry


logger = logging.getLogger(__name__)


# Type alias for confirmation modes
ConfirmationMode = Literal["always-ask", "always-approve", "llm-approve"]


def create_help_text(commands: list[AvailableCommand]) -> str:
    """Create help text for available slash commands.

    Args:
        commands: List of available slash commands

    Returns:
        Formatted help text
    """
    lines = ["Available slash commands:", ""]
    for cmd in commands:
        lines.append(f"  {cmd.name} - {cmd.description}")
    return "\n".join(lines)


def get_confirm_help_text(current_mode: ConfirmationMode) -> str:
    """Get help text for /confirm command.

    Args:
        current_mode: Current confirmation mode

    Returns:
        Formatted help text
    """
    return (
        f"Current confirmation mode: {current_mode}\n\n"
        f"Available modes:\n"
        f"  always-ask     - Ask for permission before every action\n"
        f"  always-approve - Automatically approve all actions\n"
        f"  llm-approve    - Use LLM security analyzer to "
        f"auto-approve safe actions\n\n"
        f"Usage: /confirm <mode>\n"
        f"Example: /confirm always-ask"
    )


def get_confirm_error_text(
    invalid_mode: str, current_mode: ConfirmationMode
) -> str:
    """Get error text for invalid /confirm mode.

    Args:
        invalid_mode: The invalid mode provided by user
        current_mode: Current confirmation mode

    Returns:
        Formatted error text
    """
    return (
        f"Unknown mode: {invalid_mode}\n\n"
        f"Available modes:\n"
        f"  always-ask     - Ask for permission before every action\n"
        f"  always-approve - Automatically approve all actions\n"
        f"  llm-approve    - Use LLM security analyzer to "
        f"auto-approve safe actions\n\n"
        f"Current mode: {current_mode}"
    )


def get_confirm_success_text(mode: ConfirmationMode) -> str:
    """Get success text after changing confirmation mode.

    Args:
        mode: The new confirmation mode

    Returns:
        Formatted success text
    """
    messages: dict[ConfirmationMode, str] = {
        "always-ask": (
            "Agent will ask for permission before executing every action."
        ),
        "always-approve": (
            "Agent will automatically approve all actions without asking. "
            "⚠️  Use with caution!"
        ),
        "llm-approve": (
            "Agent will use LLM security analyzer to automatically "
            "approve safe actions. You will only be asked for permission "
            "on potentially risky actions."
        ),
    }
    return f"Confirmation mode set to: {mode}\n\n{messages[mode]}"


def validate_confirmation_mode(mode_str: str) -> ConfirmationMode | None:
    """Validate and return confirmation mode.

    Args:
        mode_str: Mode string to validate

    Returns:
        ConfirmationMode if valid, None otherwise
    """
    valid_modes: list[ConfirmationMode] = [
        "always-ask",
        "always-approve",
        "llm-approve",
    ]
    normalized = mode_str.lower().strip()
    return normalized if normalized in valid_modes else None  # type: ignore[return-value]


def apply_confirmation_mode_to_conversation(
    conversation: BaseConversation,
    mode: ConfirmationMode,
    session_id: str,
) -> None:
    """Apply confirmation mode to a conversation.

    Args:
        conversation: The conversation to update
        mode: The confirmation mode to apply
        session_id: The session ID (for logging)
    """
    if mode == "always-ask":
        # Always ask for confirmation
        conversation.set_security_analyzer(LLMSecurityAnalyzer())  # type: ignore[attr-defined]
        conversation.set_confirmation_policy(AlwaysConfirm())  # type: ignore[attr-defined]
        logger.info(f"Set confirmation mode to always-ask for session {session_id}")

    elif mode == "always-approve":
        # Never ask for confirmation - auto-approve everything
        conversation.set_confirmation_policy(NeverConfirm())  # type: ignore[attr-defined]
        logger.info(
            f"Set confirmation mode to always-approve for session {session_id}"
        )

    elif mode == "llm-approve":
        # Use LLM to analyze and only confirm risky actions
        conversation.set_security_analyzer(LLMSecurityAnalyzer())  # type: ignore[attr-defined]
        conversation.set_confirmation_policy(ConfirmRisky())  # type: ignore[attr-defined]
        logger.info(f"Set confirmation mode to llm-approve for session {session_id}")


def setup_slash_commands(
    registry: SlashCommandRegistry,
    help_handler: callable,  # type: ignore[valid-type]
    confirm_handler: callable,  # type: ignore[valid-type]
) -> None:
    """Register slash commands in the registry.

    Args:
        registry: The slash command registry
        help_handler: Handler function for /help command
        confirm_handler: Handler function for /confirm command
    """
    registry.register(
        "help",
        "Show available slash commands",
        help_handler,
    )

    registry.register(
        "confirm",
        "Control confirmation mode (always-ask|always-approve|llm-approve)",
        confirm_handler,
    )
