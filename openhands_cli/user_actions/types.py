from enum import Enum
from typing import Literal

from pydantic import BaseModel

from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase


ConfirmationMode = Literal["always-ask", "always-approve", "llm-approve"]


class UserConfirmation(Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"


class ConfirmationResult(BaseModel):
    decision: UserConfirmation
    policy_change: ConfirmationPolicyBase | None = None
    reason: str = ""
