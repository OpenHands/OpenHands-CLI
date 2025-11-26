"""Welcome message utilities for OpenHands CLI textual app."""

import uuid

from rich.console import Console
from rich.panel import Panel
from textual.theme import Theme

from openhands_cli.version_check import check_for_updates


def get_openhands_banner() -> str:
    """Get the OpenHands ASCII art banner."""
    return r"""     ___                    _   _                 _
    /  _ \ _ __   ___ _ __ | | | | __ _ _ __   __| |___
    | | | | '_ \ / _ \ '_ \| |_| |/ _` | '_ \ / _` / __|
    | |_| | |_) |  __/ | | |  _  | (_| | | | | (_| \__ \
    \___ /| .__/ \___|_| |_|_| |_|\__,_|_| |_|\__,_|___/
          |_|"""


def get_welcome_message(conversation_id: str | None = None, *, theme: Theme) -> str:
    """Get the complete welcome message with version info.

    Args:
        conversation_id: Optional conversation ID to display
        theme: Theme to use for colors
    """
    # Use theme colors
    primary_color = theme.primary
    accent_color = theme.accent

    # Generate UUID if no conversation_id provided
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    # Use Rich markup for colored banner
    banner = f"[{primary_color}]{get_openhands_banner()}[/]"

    # Get version information
    version_info = check_for_updates()

    message_parts = [banner, ""]

    # Version line
    message_parts.append(f"OpenHands CLI v{version_info.current_version}")

    # Create console for rendering panels
    console = Console(width=80, legacy_windows=False)

    # Status panel
    status_panel = Panel("All set up!", width=15)
    with console.capture() as capture:
        console.print(status_panel)
    message_parts.extend(["", capture.get(), ""])

    # Conversation ID panel (always show now)
    conv_text = f"[{accent_color}]Initialized conversation[/] {conversation_id}"
    conv_panel = Panel(conv_text)
    with console.capture() as capture:
        console.print(conv_panel)
    message_parts.extend([capture.get(), ""])

    # Instructions
    message_parts.extend(
        [
            f"[{primary_color}]What do you want to build?[/]",
            "1. Ask questions, edit files, or run commands.",
            "2. Use @ to look up a file in the folder structure",
            "3. Type /help for help or / to immediately scroll through available "
            "commands",
        ]
    )

    # Update notification (if needed)
    if version_info.needs_update and version_info.latest_version:
        message_parts.extend(
            [
                "",
                f"⚠ Update available: {version_info.latest_version}",
                "Run 'uv tool upgrade openhands' to update",
            ]
        )

    return "\n".join(message_parts)
