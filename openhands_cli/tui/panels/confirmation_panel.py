"""Confirmation panel for displaying user confirmation options inline."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import ListItem, ListView, Static

from openhands_cli.tui.core.events import ConfirmationDecision
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

    When the user selects an option, the panel posts a ConfirmationDecision
    message that bubbles up to the ConversationManager for processing.
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
        **kwargs,
    ):
        """Initialize the inline confirmation panel.

        Args:
            num_actions: Number of pending actions that need confirmation
        """
        super().__init__(**kwargs)
        self.num_actions = num_actions

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

    def _remove_self(self) -> None:
        """Remove the panel from the DOM.

        Kept as a separate method to simplify unit testing.
        """
        self.remove()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle ListView selection events by posting ConfirmationDecision message.

        After posting the message, the panel removes itself from the DOM.
        """
        if event.item is None or event.item.id is None:
            return

        item_id = event.item.id

        if item_id == "accept":
            self.post_message(ConfirmationDecision(UserConfirmation.ACCEPT))
        elif item_id == "reject":
            self.post_message(ConfirmationDecision(UserConfirmation.REJECT))
        elif item_id == "always":
            self.post_message(ConfirmationDecision(UserConfirmation.ALWAYS_PROCEED))
        elif item_id == "risky":
            self.post_message(ConfirmationDecision(UserConfirmation.CONFIRM_RISKY))

        self._remove_self()
