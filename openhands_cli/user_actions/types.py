from enum import Enum

from pydantic import BaseModel

from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase


class UserConfirmation(Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"
    ALWAYS_PROCEED = "always_proceed"  # Accept and set NeverConfirm policy
    CONFIRM_RISKY = "confirm_risky"  # Accept and set ConfirmRisky policy


class ConfirmationResult(BaseModel):
    decision: UserConfirmation
    policy_change: ConfirmationPolicyBase | None = None
    reason: str = ""
