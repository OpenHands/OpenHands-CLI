"""Slash commands implementation for ACP."""

import logging

from acp.schema import AvailableCommand, AvailableCommandInput, UnstructuredCommandInput

from openhands.sdk import BaseConversation
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands_cli.acp_impl.confirmation import CONFIRMATION_MODES, ConfirmationMode
from openhands_cli.shared.slash_commands import (
    parse_slash_command as parse_slash_command,
)


logger = logging.getLogger(__name__)

VALID_CONFIRMATION_MODE: list[ConfirmationMode] = [
    "always-ask",
    "always-approve",
    "llm-approve",
]


def get_available_slash_commands() -> list[AvailableCommand]:
    """Get list of available slash commands in ACP format.

    Returns:
        List of AvailableCommand objects
    """
    # Dynamically construct mode options from CONFIRMATION_MODES
    mode_options = " | ".join(CONFIRMATION_MODES.keys())
    mode_list = "|".join(CONFIRMATION_MODES.keys())

    return [
        AvailableCommand(
            name="help",
            description="Show available slash commands",
            input=AvailableCommandInput(
                root=UnstructuredCommandInput(hint="No arguments"),
            ),
        ),
        AvailableCommand(
            name="confirm",
            description=f"Control confirmation mode ({mode_list})",
            input=AvailableCommandInput(
                root=UnstructuredCommandInput(hint=mode_options),
            ),
        ),
    ]


def create_help_text() -> str:
    """Create help text for available slash commands.

    Returns:
        Formatted help text
    """
    commands = get_available_slash_commands()
    lines = ["Available slash commands:", ""]
    for cmd in commands:
        lines.append(f"  /{cmd.name} - {cmd.description}")
    return "\n".join(lines)


def get_confirm_help_text(current_mode: ConfirmationMode) -> str:
    """Get help text for /confirm command.

    Args:
        current_mode: Current confirmation mode

    Returns:
        Formatted help text
    """
    modes_list = "\n".join(
        f"  {mode:14} - {info['short']}" for mode, info in CONFIRMATION_MODES.items()
    )
    return (
        f"Current confirmation mode: {current_mode}\n\n"
        f"Available modes:\n"
        f"{modes_list}\n\n"
        f"Usage: /confirm <mode>\n"
        f"Example: /confirm always-ask"
    )


def get_confirm_error_text(invalid_mode: str, current_mode: ConfirmationMode) -> str:
    """Get error text for invalid /confirm mode.

    Args:
        invalid_mode: The invalid mode provided by user
        current_mode: Current confirmation mode

    Returns:
        Formatted error text
    """
    modes_list = "\n".join(
        f"  {mode:14} - {info['short']}" for mode, info in CONFIRMATION_MODES.items()
    )
    return (
        f"Unknown mode: {invalid_mode}\n\n"
        f"Available modes:\n"
        f"{modes_list}\n\n"
        f"Current mode: {current_mode}"
    )


def get_confirm_success_text(mode: ConfirmationMode) -> str:
    """Get success text after changing confirmation mode.

    Args:
        mode: The new confirmation mode

    Returns:
        Formatted success text
    """
    return f"Confirmation mode set to: {mode}\n\n{CONFIRMATION_MODES[mode]['long']}"


def validate_confirmation_mode(mode_str: str) -> ConfirmationMode | None:
    """Validate and return confirmation mode.

    Args:
        mode_str: Mode string to validate

    Returns:
        ConfirmationMode if valid, None otherwise
    """
    normalized = mode_str.lower().strip()
    return normalized if normalized in VALID_CONFIRMATION_MODE else None


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
        conversation.set_security_analyzer(LLMSecurityAnalyzer())
        conversation.set_confirmation_policy(AlwaysConfirm())

    elif mode == "always-approve":
        # Never ask for confirmation - auto-approve everything
        conversation.set_security_analyzer(LLMSecurityAnalyzer())
        conversation.set_confirmation_policy(NeverConfirm())

    elif mode == "llm-approve":
        # Use LLM to analyze and only confirm risky actions
        conversation.set_security_analyzer(LLMSecurityAnalyzer())
        conversation.set_confirmation_policy(ConfirmRisky())

    logger.debug(f"Set confirmation mode to {mode} for session {session_id}")


def get_confirmation_mode_from_conversation(
    conversation: BaseConversation,
) -> ConfirmationMode:
    """Get current confirmation mode from a conversation's policy.

    Args:
        conversation: The conversation to query

    Returns:
        Current confirmation mode as a string
        ("always-ask", "always-approve", or "llm-approve")
    """
    policy = conversation.state.confirmation_policy

    if isinstance(policy, NeverConfirm):
        return "always-approve"
    elif isinstance(policy, ConfirmRisky):
        return "llm-approve"
    elif isinstance(policy, AlwaysConfirm):
        return "always-ask"
    else:
        # Default to always-ask for unknown policies
        logger.warning(
            f"Unknown confirmation policy: {type(policy)}, defaulting to always-ask"
        )
        return "always-ask"


def handle_confirm_argument(
    current_mode: ConfirmationMode, argument: str
) -> tuple[str, ConfirmationMode | None]:
    """Handle /confirm command and return response.

    This is a pure function that computes the response text and new mode
    without any side effects.

    Args:
        current_mode: Current confirmation mode for the session
        argument: Command argument (mode to set, or empty for help)

    Returns:
        Tuple of (response_text, new_mode_or_none). new_mode is None if
        no mode change should occur (help text or invalid mode).
    """
    # If no argument provided, show current state and prompt for mode
    if not argument.strip():
        return get_confirm_help_text(current_mode), None

    # Validate mode
    mode = validate_confirmation_mode(argument)
    if mode is None:
        return get_confirm_error_text(argument, current_mode), None

    # Return success message with the new mode
    return get_confirm_success_text(mode), mode


def get_unknown_command_text(command: str) -> str:
    """Get error text for unknown slash command.

    Args:
        command: The unknown command

    Returns:
        Formatted error text
    """
    commands = get_available_slash_commands()
    command_list = ", ".join(f"/{cmd.name}" for cmd in commands)
    return (
        f"Unknown command: /{command}\n\n"
        f"Available commands: {command_list}\n"
        f"Use /help for more information."
    )
