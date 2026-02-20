"""Confirmation settings modal for OpenHands CLI."""

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmationPolicyBase,
    ConfirmRisky,
    NeverConfirm,
)


# Policy display names for notifications
POLICY_DISPLAY_NAMES: dict[type[ConfirmationPolicyBase], str] = {
    NeverConfirm: "Always approve actions (no confirmation)",
    AlwaysConfirm: "Confirm every action",
    ConfirmRisky: "Confirm high-risk actions only",
}


def get_policy_display_name(policy: ConfirmationPolicyBase) -> str:
    """Get a human-readable display name for a confirmation policy."""
    return POLICY_DISPLAY_NAMES.get(type(policy), "Custom policy")


class ConfirmationSettingsModal(ModalScreen):
    """Modal screen for selecting confirmation settings."""

    CSS_PATH = "confirmation_modal.tcss"

    def __init__(
        self,
        current_policy: ConfirmationPolicyBase,
        on_policy_selected: Callable[[ConfirmationPolicyBase], None],
        **kwargs,
    ):
        """Initialize the confirmation settings modal.

        Args:
            current_policy: The currently active confirmation policy
            on_policy_selected: Callback to invoke when a policy is selected
        """
        super().__init__(**kwargs)
        self.current_policy = current_policy
        self.on_policy_selected = on_policy_selected

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        with Container(id="dialog"):
            with Vertical():
                yield Label("Confirmation Settings", id="title")
                yield Static(
                    "Select how you want to handle action confirmations:",
                    id="description",
                )

                # Create ListView with confirmation options
                list_items = []
                initial_index = 0

                # Option 1: Always approve action (no confirmation)
                list_items.append(
                    ListItem(
                        Static("🚀 Always approve actions (no confirmation)"),
                        id="never_confirm",
                    )
                )
                if isinstance(self.current_policy, NeverConfirm):
                    initial_index = 0

                # Option 2: Confirm every action
                list_items.append(
                    ListItem(
                        Static("🔍 Confirm every action"),
                        id="always_confirm",
                    )
                )
                if isinstance(self.current_policy, AlwaysConfirm):
                    initial_index = 1

                # Option 3: Confirm high-risk actions (LLM approve low/medium)
                list_items.append(
                    ListItem(
                        Static("⚠️  Confirm high-risk actions only"),
                        id="confirm_risky",
                    )
                )
                if isinstance(self.current_policy, ConfirmRisky):
                    initial_index = 2

                yield ListView(
                    *list_items,
                    id="options_list",
                    initial_index=initial_index,
                )

                yield Static(
                    "Press Enter to select, Escape to cancel",
                    id="instructions",
                )

    def on_mount(self) -> None:
        """Focus the ListView when the modal is mounted."""
        # Defer until after the DOM is fully composed
        self.call_after_refresh(self._focus_list)

    def _focus_list(self) -> None:
        """Focus the options ListView once it's available."""
        listview = self.query_one("#options_list", ListView)
        listview.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle ListView selection events."""
        item_id = event.item.id

        # Create the appropriate policy based on selection
        if item_id == "never_confirm":
            policy = NeverConfirm()
        elif item_id == "always_confirm":
            policy = AlwaysConfirm()
        elif item_id == "confirm_risky":
            policy = ConfirmRisky()
        else:
            return  # Unknown selection

        # Dismiss the modal first
        self.dismiss()

        # Call the callback to set the policy
        self.on_policy_selected(policy)

        # Show notification
        policy_name = get_policy_display_name(policy)
        self.app.notify(f"Confirmation policy set to: {policy_name}")

    def key_escape(self) -> None:
        """Handle Escape key to close modal without changes."""
        self.dismiss()
