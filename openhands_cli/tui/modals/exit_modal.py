"""Exit confirmation modal for OpenHands CLI."""

from collections.abc import Callable

from openhands_cli.tui.modals.binary_confirmation_modal import BinaryConfirmationModal


class ExitConfirmationModal(BinaryConfirmationModal[None]):
    """Screen with a dialog to confirm exit."""

    def __init__(
        self,
        on_exit_confirmed: Callable[[], None] | None = None,
        on_exit_cancelled: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the exit confirmation modal.

        Args:
            on_exit_confirmed: Callback to invoke when exit is confirmed
            on_exit_cancelled: Callback to invoke when exit is cancelled
        """
        super().__init__(
            prompt="Terminate session?",
            confirm_label="Yes, proceed",
            cancel_label="No, dismiss",
            **kwargs,
        )
        self.on_exit_confirmed = on_exit_confirmed or (lambda: self.app.exit())
        self.on_exit_cancelled = on_exit_cancelled

    def handle_choice(self, confirmed: bool) -> None:
        if confirmed:
            try:
                self.on_exit_confirmed()
            except Exception as e:
                self.notify(f"Error during exit confirmation: {e}", severity="error")
            return

        if self.on_exit_cancelled:
            try:
                self.on_exit_cancelled()
            except Exception as e:
                self.notify(f"Error during exit cancellation: {e}", severity="error")
