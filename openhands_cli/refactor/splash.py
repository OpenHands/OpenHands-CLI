"""Welcome message utilities for OpenHands CLI textual app."""

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

    # Use Rich markup for colored banner
    banner = f"[{primary_color}]{get_openhands_banner()}[/]"

    # Get version information
    version_info = check_for_updates()

    message_parts = [banner, ""]

    if conversation_id:
        # Use accent color for "initialize conversation" text
        message_parts.append(
            f"[{accent_color}]Initialized conversation {conversation_id}[/]"
        )
    else:
        message_parts.append("Welcome to OpenHands CLI!")

    message_parts.append("")
    message_parts.append(f"Version: {version_info.current_version}")

    if version_info.needs_update and version_info.latest_version:
        message_parts.append(f"⚠ Update available: {version_info.latest_version}")
        message_parts.append("Run 'uv tool upgrade openhands' to update")

    message_parts.extend(
        [
            "",
            "Let's start building!",
            "What do you want to build? Type /help for help",
            "",
            "Press any key to continue...",
        ]
    )

    return "\n".join(message_parts)
