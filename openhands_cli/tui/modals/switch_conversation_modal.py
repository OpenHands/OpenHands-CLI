"""Switch conversation confirmation modal for OpenHands CLI."""

from __future__ import annotations

from openhands_cli.tui.modals.binary_confirmation_modal import BinaryConfirmationModal


class SwitchConversationModal(BinaryConfirmationModal[bool]):
    """Screen with a dialog to confirm switching conversations."""

    def __init__(
        self,
        *,
        prompt: str,
        **kwargs,
    ) -> None:
        super().__init__(
            prompt=prompt,
            confirm_label="Yes, switch",
            cancel_label="No, stay",
            **kwargs,
        )

    def get_dismiss_result(self, confirmed: bool) -> bool:
        return confirmed
