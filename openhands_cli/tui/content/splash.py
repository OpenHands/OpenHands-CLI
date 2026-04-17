"""Welcome message utilities for OpenHands CLI textual app."""

from textual.theme import Theme

from openhands_cli import __version__
from openhands_cli.version_check import VersionInfo


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
    banner_lines = [
        r"     ___                    _   _                 _     ",
        r"    /  _ \ _ __   ___ _ __ | | | | __ _ _ __   __| |___",
        r"    | | | | '_ \ / _ \ '_ \| |_| |/ _` | '_ \ / _` / __|",
        r"    | |_| | |_) |  __/ | | |  _  | (_| | | | | (_| \__ \ ",
        r"    \___ /| .__/ \___|_| |_|_| |_|\__,_|_| |_|\__,_|___/",
        r"          |_|                                           ",
    ]
    max_length = max(len(line) for line in banner_lines)
    padded_lines = [line.ljust(max_length) for line in banner_lines]
    return "\n".join(padded_lines)


def get_version_text(version_info: VersionInfo | None = None) -> str:
    """Get the splash version text.

    Args:
        version_info: Optional version information from a background update check.
    """
    current_version = version_info.current_version if version_info else __version__
    return f"OpenHands CLI v{current_version}"


def get_update_notice(
    *, theme: Theme, version_info: VersionInfo | None = None
) -> str | None:
    """Get the update notice text for the splash screen."""
    if (
        not version_info
        or not version_info.needs_update
        or not version_info.latest_version
    ):
        return None

    return (
        f"[{theme.primary}]⚠ Update available: {version_info.latest_version}[/]\n"
        "Run 'uv tool upgrade openhands' to update"
    )


def get_critic_notice(*, theme: Theme, has_critic: bool) -> str | None:
    """Get the critic notice text for the splash screen."""
    if not has_critic:
        return None

    title = (
        f"\n[{theme.primary}]Experimental Feature: Critic + "
        "Iterative Refinement Mode[/]\n"
    )
    details = (
        "[dim]Using OpenHands provider enables a free critic to predict task success. "
        "Enable Iterative Refinement in settings to auto-prompt the agent when work "
        "appears incomplete. Anonymized data collected. Disable in settings.[/dim]"
    )
    return title + details


def get_splash_content(
    conversation_id: str,
    *,
    theme: Theme,
    has_critic: bool = False,
    version_info: VersionInfo | None = None,
) -> dict:
    """Get structured splash screen content for native Textual widgets.

    Args:
        conversation_id: Optional conversation ID to display
        theme: Theme to use for colors
        has_critic: Whether the agent has a critic configured
        version_info: Optional version information from a background update check
    """
    primary_color = theme.primary
    banner_lines = get_openhands_banner().split("\n")
    colored_banner_lines = [f"[{primary_color}]{line}[/]" for line in banner_lines]
    banner = "\n".join(colored_banner_lines)

    return {
        "banner": banner,
        "version": get_version_text(version_info),
        "status_text": "All set up!",
        "conversation_text": get_conversation_text(conversation_id, theme=theme),
        "conversation_id": conversation_id,
        "instructions_header": f"[{primary_color}]What do you want to build?[/]",
        "instructions": [
            "1. Ask questions, edit files, or run commands.",
            "2. Use @ to look up a file in the folder structure",
            (
                "3. Type /help for help, /feedback to leave anonymous feedback, "
                "or / to scroll through available commands"
            ),
        ],
        "update_notice": get_update_notice(theme=theme, version_info=version_info),
        "critic_notice": get_critic_notice(theme=theme, has_critic=has_critic),
    }
