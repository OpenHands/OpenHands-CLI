"""ConfirmationPolicyService - sync policy to state and current conversation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase


if TYPE_CHECKING:
    from openhands_cli.tui.core.runner_registry import RunnerRegistry
    from openhands_cli.tui.core.state import ConversationContainer


class ConfirmationPolicyService:
    def __init__(
        self,
        *,
        state: ConversationContainer,
        runners: RunnerRegistry,
    ) -> None:
        self._state = state
        self._runners = runners

    def set_policy(self, policy: ConfirmationPolicyBase) -> None:
        runner = self._runners.current
        if runner is not None and runner.conversation is not None:
            runner.conversation.set_confirmation_policy(policy)
        self._state.confirmation_policy = policy
