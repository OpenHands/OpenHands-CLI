import html
import os
from prompt_toolkit import HTML, print_formatted_text

from openhands.sdk.security.confirmation_policy import (
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.risk import SecurityRisk
from openhands.tools.file_editor.definition import FileEditorAction
from openhands_cli.locations import WORK_DIR
from openhands_cli.user_actions.types import ConfirmationResult, UserConfirmation
from openhands_cli.user_actions.utils import cli_confirm, cli_text_input


def format_action_content(action_obj) -> str:
    """Format action content with paths replaced with relative paths to CWD.
    
    Args:
        action_obj: The action object (e.g., FileEditorAction), or None
        
    Returns:
        Formatted string representation of the action with truncated paths,
        truncated to 100 characters with newlines replaced by spaces
    """
    if action_obj is None:
        return "[unknown action]"
    
    result = str(action_obj)
    
    if isinstance(action_obj, FileEditorAction) and action_obj.path:
        try:
            relative_path = os.path.relpath(action_obj.path, WORK_DIR)
            result = result.replace(action_obj.path, relative_path)
        except (ValueError, OSError):
            pass
    
    return result[:100].replace("\n", " ")


def ask_user_confirmation(
    pending_actions: list, using_risk_based_policy: bool = False
) -> ConfirmationResult:
    """Ask user to confirm pending actions.

    Args:
        pending_actions: List of pending actions from the agent

    Returns:
        ConfirmationResult with decision, optional policy_change, and reason
    """

    if not pending_actions:
        return ConfirmationResult(decision=UserConfirmation.ACCEPT)

    print_formatted_text(
        HTML(
            f"<yellow>🔍 Agent created {len(pending_actions)} action(s) and is "
            f"waiting for confirmation:</yellow>"
        )
    )

    for i, action in enumerate(pending_actions, 1):
        tool_name = getattr(action, "tool_name", "[unknown tool]")
        action_obj = getattr(action, "action", None)
        action_content = format_action_content(action_obj)
        print_formatted_text(
            HTML(f"<grey>  {i}. {tool_name}: {html.escape(action_content)}...</grey>")
        )

    question = "Choose an option:"
    options = [
        "Yes, proceed",
        "Reject",
        "Always proceed (don't ask again)",
    ]

    if not using_risk_based_policy:
        options.append("Auto-confirm LOW/MEDIUM risk, ask for HIGH risk")

    try:
        index = cli_confirm(question, options, escapable=True)
    except (EOFError, KeyboardInterrupt):
        print_formatted_text(HTML("\n<red>No input received; pausing agent.</red>"))
        return ConfirmationResult(decision=UserConfirmation.DEFER)

    if index == 0:
        return ConfirmationResult(decision=UserConfirmation.ACCEPT)
    elif index == 1:
        # Handle "Reject" option with optional reason
        try:
            reason = cli_text_input("Reason (and let OpenHands know why): ").strip()
        except (EOFError, KeyboardInterrupt):
            return ConfirmationResult(decision=UserConfirmation.DEFER)

        return ConfirmationResult(decision=UserConfirmation.REJECT, reason=reason)
    elif index == 2:
        return ConfirmationResult(
            decision=UserConfirmation.ACCEPT, policy_change=NeverConfirm()
        )
    elif index == 3:
        return ConfirmationResult(
            decision=UserConfirmation.ACCEPT,
            policy_change=ConfirmRisky(threshold=SecurityRisk.HIGH),
        )

    return ConfirmationResult(decision=UserConfirmation.REJECT)
