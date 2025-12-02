"""Confirmation panel for displaying user confirmation options in a side panel."""

import html
from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Static

from openhands_cli.user_actions.types import UserConfirmation


class ConfirmationPanel(Container):
    """A side panel that displays pending actions and confirmation options."""

    def __init__(
        self,
        pending_actions: list,
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
        with Vertical():
            # Header
            yield Static(
                f"🔍 Agent created {len(self.pending_actions)} action(s) and is "
                "waiting for confirmation:",
                classes="confirmation-header",
            )

            # Actions list
            with Container(classes="actions-container"):
                for i, action in enumerate(self.pending_actions, 1):
                    tool_name = getattr(action, "tool_name", "[unknown tool]")
                    action_content = (
                        str(getattr(action, "action", ""))[:100].replace("\n", " ")
                        or "[unknown action]"
                    )
                    yield Static(
                        f"{i}. {tool_name}: {html.escape(action_content)}...",
                        classes="action-item",
                    )

            # Buttons
            with Horizontal(classes="button-container"):
                yield Button("Yes, proceed", id="btn_accept", variant="success")
                yield Button("Reject", id="btn_reject", variant="error")
                yield Button("Always proceed", id="btn_always", variant="primary")
                yield Button(
                    "Auto-confirm LOW/MEDIUM", id="btn_risky", variant="default"
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "btn_accept":
            self.confirmation_callback(UserConfirmation.ACCEPT)
        elif button_id == "btn_reject":
            self.confirmation_callback(UserConfirmation.REJECT)
        elif button_id == "btn_always":
            # Accept and set NeverConfirm policy
            self.confirmation_callback(UserConfirmation.ALWAYS_PROCEED)
        elif button_id == "btn_risky":
            # Accept and set ConfirmRisky policy
            self.confirmation_callback(UserConfirmation.CONFIRM_RISKY)


class ConfirmationSidePanel(Container):
    """A container that shows the confirmation panel on the right side.

    Uses a dashed border for visual separation.
    """

    DEFAULT_CSS = """
    ConfirmationSidePanel {
        width: 40%;
        height: 100%;
        border-left: dashed $secondary;
        background: $surface;
        padding: 1;
        margin-left: 1;
    }

    .confirmation-header {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }

    .actions-container {
        height: auto;
        margin-bottom: 1;
    }

    .action-item {
        color: $foreground;
        margin-bottom: 1;
        padding: 0 1;
        background: $background;
        border: solid $secondary;
    }

    .button-container {
        height: auto;
        align: center middle;
    }

    .button-container Button {
        margin: 0 1;
        min-width: 12;
    }
    """

    def __init__(
        self,
        pending_actions: list,
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
