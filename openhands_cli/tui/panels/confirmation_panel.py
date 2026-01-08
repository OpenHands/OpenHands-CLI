"""Confirmation panel for displaying user confirmation options inline."""

from collections.abc import Callable
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import ListItem, ListView, Static

from openhands_cli.tui.panels.confirmation_panel_style import (
    INLINE_CONFIRMATION_PANEL_STYLE,
)
from openhands_cli.user_actions.types import UserConfirmation


class ConfirmationOption(Static):
    """A confirmation option that shows > when highlighted."""

    def __init__(self, label: str, **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.is_highlighted = False

    def on_mount(self) -> None:
        """Set initial display."""
        self._update_display()

    def set_highlighted(self, highlighted: bool) -> None:
        """Update the highlighted state."""
        self.is_highlighted = highlighted
        self._update_display()

    def _update_display(self) -> None:
        """Update the display based on highlighted state."""
        if self.is_highlighted:
            self.update(f"> {self.label}")
        else:
            self.update(f"  {self.label}")


class InlineConfirmationPanel(Container):
    """An inline panel that displays only confirmation options.

    This panel is designed to be mounted in the main display area,
    underneath the latest action event collapsible. It only shows
    the confirmation options since the action details are already
    visible in the action event collapsible above.
    """

    DEFAULT_CSS = INLINE_CONFIRMATION_PANEL_STYLE

    OPTIONS: ClassVar[list[tuple[str, str]]] = [
        ("accept", "Yes"),
        ("reject", "No"),
        ("always", "Always"),
        ("risky", "Auto LOW/MED"),
    ]

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
        with Vertical(classes="inline-confirmation-content"):
            # Header/prompt
            yield Static(
                f"🔍 Confirm {self.num_actions} action(s)?",
                classes="inline-confirmation-header",
            )

            # Options ListView (vertical)
            yield ListView(
                *[
                    ListItem(
                        ConfirmationOption(label, id=f"option-{item_id}"), id=item_id
                    )
                    for item_id, label in self.OPTIONS
                ],
                classes="inline-confirmation-options",
                initial_index=0,
                id="inline-confirmation-listview",
            )

    def on_mount(self) -> None:
        """Focus the ListView when the panel is mounted."""
        listview = self.query_one("#inline-confirmation-listview", ListView)
        listview.focus()
        # Set initial highlight on first option
        self._update_option_highlights(0)

    def _update_option_highlights(self, highlighted_index: int) -> None:
        """Update the > marker on options based on highlighted index."""
        for i, (item_id, _) in enumerate(self.OPTIONS):
            option = self.query_one(f"#option-{item_id}", ConfirmationOption)
            option.set_highlighted(i == highlighted_index)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle ListView highlight changes to update > markers."""
        if event.item is not None:
            listview = self.query_one("#inline-confirmation-listview", ListView)
            self._update_option_highlights(listview.index or 0)

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
