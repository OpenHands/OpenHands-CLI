"""Display utilities for conversation listing."""

from datetime import datetime

from rich.console import Console

from openhands_cli.conversations.lister import ConversationLister
from openhands_cli.theme import OPENHANDS_THEME


console = Console()


def display_recent_conversations(limit: int = 15) -> None:
    """Display a list of recent conversations in the terminal.

    Args:
        limit: Maximum number of conversations to display (default: 15)
    """
    lister = ConversationLister()
    conversations = lister.list()

    if not conversations:
        console.print("No conversations found.", style=OPENHANDS_THEME.warning)
        console.print(
            "Start a new conversation with: openhands",
            style=f"{OPENHANDS_THEME.secondary} dim",
        )
        return

    # Limit to the requested number of conversations
    conversations = conversations[:limit]

    console.print("Recent Conversations:", style=f"{OPENHANDS_THEME.primary} bold")
    console.print("-" * 80, style=f"{OPENHANDS_THEME.secondary} dim")

    for i, conv in enumerate(conversations, 1):
        # Format the date nicely
        date_str = _format_date(conv.created_date)

        # Truncate long prompts
        prompt_preview = _truncate_prompt(conv.first_user_prompt)

        # Format the conversation entry
        console.print(f"{i:2d}. ", style=f"{OPENHANDS_THEME.primary} bold", end="")
        console.print(f"{conv.id} ", style=OPENHANDS_THEME.accent, end="")
        console.print(f"({date_str})", style=f"{OPENHANDS_THEME.secondary} dim")

        if prompt_preview:
            console.print(
                f"    {prompt_preview}", style=OPENHANDS_THEME.foreground, markup=False
            )
        else:
            console.print(
                "    (No user message)", style=f"{OPENHANDS_THEME.secondary} dim"
            )

        console.print()  # Add spacing between entries

    console.print("-" * 80, style=f"{OPENHANDS_THEME.secondary} dim")
    console.print(
        "To resume a conversation, use: ",
        style=f"{OPENHANDS_THEME.secondary} dim",
        end="",
    )
    console.print(
        "openhands --resume <conversation-id>",
        style=f"{OPENHANDS_THEME.primary} bold",
    )


def _format_date(dt: datetime) -> str:
    """Format a datetime for display.

    Args:
        dt: The datetime to format

    Returns:
        Formatted date string
    """
    now = datetime.now()
    diff = now - dt

    if diff.days == 0:
        if diff.seconds < 3600:  # Less than 1 hour
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:  # Less than 1 day
            hours = diff.seconds // 3600
            return f"{hours}h ago"
    elif diff.days == 1:
        return "yesterday"
    elif diff.days < 7:
        return f"{diff.days} days ago"
    else:
        return dt.strftime("%Y-%m-%d")


def _truncate_prompt(prompt: str | None, max_length: int = 60) -> str:
    """Truncate a prompt for display.

    Args:
        prompt: The prompt to truncate
        max_length: Maximum length before truncation

    Returns:
        Truncated prompt string
    """
    if not prompt:
        return ""

    # Replace newlines with spaces for display
    prompt = prompt.replace("\n", " ").replace("\r", " ")

    if len(prompt) <= max_length:
        return prompt

    return prompt[: max_length - 3] + "..."
