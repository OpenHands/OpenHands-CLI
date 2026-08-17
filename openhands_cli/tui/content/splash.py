"""Welcome message utilities for OpenHands CLI textual app."""

from typing import TypedDict

from textual.theme import Theme

from openhands_cli.version_check import check_for_updates


class SplashContentData(TypedDict):
    """Structured content data for splash screen display."""

    banner: str
    version: str
    status_text: str
    conversation_text: str
    conversation_id: str
    instructions_header: str
    instructions: list[str]
    update_notice: str | None
    critic_notice: str | None


def get_conversation_text(conversation_id: str, *, theme: Theme) -> str:
    """Get the formatted conversation initialization text.

    Args:
        conversation_id: The conversation ID to display
        theme: Theme to use for colors

    Returns:
        Formatted string with conversation initialization message
    """
    return f"[{theme.accent}]Initialized conversation[/] {conversation_id}"


def get_openhands_banner() -> str:
    """Get the OpenHands ASCII art banner."""
    # ASCII art with consistent line lengths for proper alignment
    banner_lines = [
        r"     ___                    _   _                 _     ",
        r"    /  _ \ _ __   ___ _ __ | | | | __ _ _ __   __| |___",
        r"    | | | | '_ \ / _ \ '_ \| |_| |/ _` | '_ \ / _` / __|",
        r"    | |_| | |_) |  __/ | | |  _  | (_| | | | | (_| \__ \ ",
        r"    \___ /| .__/ \___|_| |_|_| |_|\__,_|_| |_|\__,_|___/",
        r"          |_|                                           ",
    ]

    # Find the maximum line length
    max_length = max(len(line) for line in banner_lines)

    # Pad all lines to the same length for consistent alignment
    padded_lines = [line.ljust(max_length) for line in banner_lines]

    return "\n".join(padded_lines)


def get_splash_content(
    conversation_id: str,
    *,
    theme: Theme,
    has_critic: bool = False,
) -> SplashContentData:
    """Get structured splash screen content for native Textual widgets.

    Args:
        conversation_id: Optional conversation ID to display
        theme: Theme to use for colors
        has_critic: Whether the agent has a critic configured
    """
    primary_color = theme.primary

    banner_lines = get_openhands_banner().split("\n")
    colored_banner_lines = [f"[{primary_color}]{line}[/]" for line in banner_lines]
    banner = "\n".join(colored_banner_lines)

    version_info = check_for_updates()

    update_notice: str | None = None
    if version_info.needs_update and version_info.latest_version:
        update_notice = (
            f"[{primary_color}]⚠ Update available: {version_info.latest_version}[/]\n"
            "Run 'uv tool upgrade openhands' to update"
        )

    critic_notice: str | None = None
    if has_critic:
        critic_notice = (
            f"\n[{primary_color}]Experimental Feature: "
            "Critic + Iterative Refinement Mode[/]\n"
            "[dim]Using OpenHands provider enables a free critic to predict task "
            "success. Enable Iterative Refinement in settings to auto-prompt the "
            "agent when work appears incomplete. "
            "Anonymized data collected. Disable in settings.[/dim]"
        )

    return SplashContentData(
        banner=banner,
        version=f"OpenHands CLI v{version_info.current_version}",
        status_text="All set up!",
        conversation_text=get_conversation_text(conversation_id, theme=theme),
        conversation_id=conversation_id,
        instructions_header=f"[{primary_color}]What do you want to build?[/]",
        instructions=[
            "1. Ask questions, edit files, or run commands.",
            "2. Use @ to look up a file in the folder structure",
            (
                "3. Type /help for help, /feedback to leave anonymous feedback, "
                "or / to scroll through available commands"
            ),
        ],
        update_notice=update_notice,
        critic_notice=critic_notice,
    )
