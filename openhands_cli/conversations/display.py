"""Display utilities for conversation listing."""

from datetime import datetime

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.conversations.lister import ConversationLister


def display_recent_conversations(limit: int = 15) -> None:
    """Display a list of recent conversations in the terminal.

    Args:
        limit: Maximum number of conversations to display (default: 15)
    """
    lister = ConversationLister()
    conversations = lister.list()

    if not conversations:
        print_formatted_text(HTML("<yellow>No conversations found.</yellow>"))
        print_formatted_text(
            HTML("<dim>Start a new conversation with: openhands</dim>")
        )
        return

    # Limit to the requested number of conversations
    conversations = conversations[:limit]

    print_formatted_text(HTML("<bold>Recent Conversations:</bold>"))
    print_formatted_text(HTML("<dim>" + "-" * 80 + "</dim>"))

    for i, conv in enumerate(conversations, 1):
        # Format the date nicely
        date_str = _format_date(conv.created_date)

        # Truncate long prompts
        prompt_preview = _truncate_prompt(conv.first_user_prompt)

        # Format the conversation entry
        print_formatted_text(
            HTML(f"<bold>{i:2d}.</bold> <cyan>{conv.id}</cyan> <dim>({date_str})</dim>")
        )

        if prompt_preview:
            print_formatted_text(HTML(f"    <white>{prompt_preview}</white>"))
        else:
            print_formatted_text(HTML("    <dim>(No user message)</dim>"))

        print()  # Add spacing between entries

    print_formatted_text(HTML("<dim>" + "-" * 80 + "</dim>"))
    print_formatted_text(
        HTML(
            "<dim>To resume a conversation, use: </dim>"
            "<bold>openhands --resume &lt;conversation-id&gt;</bold>"
        )
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
