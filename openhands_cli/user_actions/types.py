from enum import Enum

from pydantic import BaseModel

from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase


class UserConfirmation(Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"
    ALWAYS_PROCEED = "always_proceed"
    CONFIRM_RISKY = "confirm_risky"


class ConfirmationResult(BaseModel):
    decision: UserConfirmation
    policy_change: ConfirmationPolicyBase | None = None
    reason: str = ""
