"""Confirmation panel for displaying user confirmation options inline."""

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import ListItem, ListView, Static

from openhands_cli.tui.panels.confirmation_panel_style import (
    INLINE_CONFIRMATION_PANEL_STYLE,
)
from openhands_cli.user_actions.types import UserConfirmation


class InlineConfirmationPanel(Container):
    """An inline panel that displays only confirmation options.

    This panel is designed to be mounted in the main display area,
    underneath the latest action event collapsible. It only shows
    the confirmation options since the action details are already
    visible in the action event collapsible above.
    """

    DEFAULT_CSS = INLINE_CONFIRMATION_PANEL_STYLE

    def __init__(
        self,
        num_actions: int,
        confirmation_callback: Callable[[UserConfirmation], None],
        **kwargs,
    ):
        """Initialize the inline confirmation panel.

        Args:
            num_actions: Number of pending actions that need confirmation
            confirmation_callback: Callback function to call with user's decision
        """
        super().__init__(**kwargs)
        self.num_actions = num_actions
        self.confirmation_callback = confirmation_callback

    def compose(self) -> ComposeResult:
        """Create the inline confirmation panel layout."""
        with Horizontal(classes="inline-confirmation-content"):
            # Header/prompt
            yield Static(
                f"🔍 Confirm {self.num_actions} action(s)? ",
                classes="inline-confirmation-header",
            )

            # Options ListView (horizontal)
            yield ListView(
                ListItem(Static("✅ Yes"), id="accept"),
                ListItem(Static("❌ No"), id="reject"),
                ListItem(Static("🔄 Always"), id="always"),
                ListItem(Static("⚠️ Auto LOW/MED"), id="risky"),
                classes="inline-confirmation-options",
                initial_index=0,
                id="inline-confirmation-listview",
            )

    def on_mount(self) -> None:
        """Focus the ListView when the panel is mounted."""
        listview = self.query_one("#inline-confirmation-listview", ListView)
        listview.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle ListView selection events."""
        item_id = event.item.id

        if item_id == "accept":
            self.confirmation_callback(UserConfirmation.ACCEPT)
        elif item_id == "reject":
            self.confirmation_callback(UserConfirmation.REJECT)
        elif item_id == "always":
            # Accept and set NeverConfirm policy
            self.confirmation_callback(UserConfirmation.ALWAYS_PROCEED)
        elif item_id == "risky":
            # Accept and set ConfirmRisky policy
            self.confirmation_callback(UserConfirmation.CONFIRM_RISKY)
