"""UI event messages for App ↔ ConversationManager communication.

Minimal events for interactions that require App-level handling:
- RequestSwitchConfirmation: App shows modal, sends SwitchConfirmed back

Most UI state is handled reactively via ConversationState:
- conversation_id=None: InputField disables, App shows loading state
- conversation_id=UUID: InputField enables, normal operation

ConversationManager can call self.app.notify() and self.run_worker() directly.
"""

import uuid

from textual.message import Message


class RequestSwitchConfirmation(Message):
    """Request App to show switch confirmation modal.

    Flow:
    1. ConversationManager posts RequestSwitchConfirmation(target_id)
    2. App shows modal asking user to confirm
    3. App posts SwitchConfirmed(target_id, confirmed) back to ConversationManager
    """

    def __init__(self, target_id: uuid.UUID) -> None:
        super().__init__()
        self.target_id = target_id
