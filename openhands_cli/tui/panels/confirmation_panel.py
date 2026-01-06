"""Confirmation panel for displaying user confirmation options in a side panel."""

import html
from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import ListItem, ListView, Static

from openhands.sdk.event import ActionEvent
from openhands_cli.tui.panels.confirmation_panel_style import (
    CONFIRMATION_SIDE_PANEL_STYLE,
)
from openhands_cli.user_actions.types import UserConfirmation


class ConfirmationPanel(Container):
    """A side panel that displays pending actions and confirmation options.

    All content is placed in a vertical layout that can be scrolled
    when the content exceeds the available space.
    """

    def __init__(
        self,
        pending_actions: list[ActionEvent],
        confirmation_callback: Callable[[UserConfirmation], None],
        **kwargs,
    ):
        """Initialize the confirmation panel.

        Args:
            pending_actions: List of pending actions that need confirmation
            confirmation_callback: Callback function to call with user's decision
        """
        super().__init__(**kwargs)
        self.pending_actions = pending_actions
        self.confirmation_callback = confirmation_callback

    def compose(self) -> ComposeResult:
        """Create the confirmation panel layout."""
        with Vertical(classes="confirmation-content"):
            # Header
            yield Static(
                f"🔍 Agent created {len(self.pending_actions)} action(s) and is "
                "waiting for confirmation:",
                classes="confirmation-header",
            )

            # Actions list
            with Container(classes="actions-container"):
                for i, action in enumerate(self.pending_actions, 1):
                    tool_name = action.tool_name
                    action_content = (
                        str(action.action.visualize) if action.action else ""
                    )
                    yield Static(
                        f"{i}. {tool_name}: {html.escape(action_content)}...",
                        classes="action-item",
                    )

            # Instructions
            yield Static(
                "Use ↑/↓ to navigate, Enter to select:",
                classes="confirmation-instructions",
            )

            # Options ListView
            yield ListView(
                ListItem(Static("✅ Yes, proceed"), id="accept"),
                ListItem(Static("❌ Reject"), id="reject"),
                ListItem(Static("🔄 Always proceed"), id="always"),
                ListItem(Static("⚠️  Auto-confirm LOW/MEDIUM"), id="risky"),
                classes="confirmation-options",
                initial_index=0,
                id="confirmation-listview",
            )

    def on_mount(self) -> None:
        """Focus the ListView when the panel is mounted."""
        listview = self.query_one("#confirmation-listview", ListView)
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


class ConfirmationSidePanel(VerticalScroll):
    """A scrollable container that shows the confirmation panel on the right side.

    The entire panel content is scrollable, allowing users to scroll down
    to see the confirmation buttons when the action content is too long.
    """

    DEFAULT_CSS = CONFIRMATION_SIDE_PANEL_STYLE

    def __init__(
        self,
        pending_actions: list[ActionEvent],
        confirmation_callback: Callable[[UserConfirmation], None],
        **kwargs,
    ):
        """Initialize the side panel.

        Args:
            pending_actions: List of pending actions that need confirmation
            confirmation_callback: Callback function to call with user's decision
        """
        super().__init__(**kwargs)
        self.pending_actions = pending_actions
        self.confirmation_callback = confirmation_callback

    def compose(self) -> ComposeResult:
        """Create the side panel layout."""
        yield ConfirmationPanel(
            self.pending_actions,
            self.confirmation_callback,
        )
