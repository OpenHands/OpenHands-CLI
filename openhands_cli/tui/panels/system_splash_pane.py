"""System splash content for the main chat view."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static


class SystemSplashPane(Container):
    """Container that renders system-level splash content."""

    DEFAULT_CSS = """
    SystemSplashPane {
        height: auto;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        # ASCII/branding banner shown on start.
        yield Static(id="splash_banner", classes="splash-banner")
        # CLI version line.
        yield Static(id="splash_version", classes="splash-version")
        # Status block (env/mode hints).
        yield Static(id="splash_status", classes="status-panel")
        # Current conversation identifier.
        yield Static(id="splash_conversation", classes="conversation-panel")
        # Instructions header.
        yield Static(
            id="splash_instructions_header", classes="splash-instruction-header"
        )
        # Instructions text.
        yield Static(id="splash_instructions", classes="splash-instruction")
        # Update notice (if available).
        yield Static(id="splash_update_notice", classes="splash-update-notice")
        # Critic notice (if available).
        yield Static(id="splash_critic_notice", classes="splash-critic-notice")
