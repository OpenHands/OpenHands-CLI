"""UI event messages for App ↔ ConversationManager communication.

Minimal events for interactions that require App-level handling:
- RequestSwitchConfirmation: App shows modal, sends SwitchConfirmed back
- ShowConfirmationPanel: Request App to mount confirmation panel
- ConfirmationDecision: User made a decision on pending actions

Most UI state is handled reactively via ConversationContainer:
- conversation_id=None: InputField disables, App shows loading state
- conversation_id=UUID: InputField enables, normal operation

ConversationManager can call self.app.notify() and self.run_worker() directly.
"""

import uuid
from typing import TYPE_CHECKING

from textual.message import Message

from openhands_cli.user_actions.types import UserConfirmation


if TYPE_CHECKING:
    from openhands.sdk.event import ActionEvent


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


class ShowConfirmationPanel(Message):
    """Request App to show the inline confirmation panel.

    Flow:
    1. ConversationRunner posts ShowConfirmationPanel via ConversationManager
    2. App mounts the InlineConfirmationPanel in the scroll view
    3. User interacts with the panel
    4. Panel posts ConfirmationDecision which bubbles to ConversationManager
    """

    def __init__(self, pending_actions: list["ActionEvent"]) -> None:
        super().__init__()
        self.pending_actions = pending_actions


class ConfirmationDecision(Message):
    """User made a decision on pending actions.

    Flow:
    1. InlineConfirmationPanel posts ConfirmationDecision when user selects an option
    2. Message bubbles up to ConversationManager
    3. ConversationManager processes the decision and resumes the conversation
    """

    def __init__(self, decision: UserConfirmation) -> None:
        super().__init__()
        self.decision = decision
