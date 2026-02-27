"""ConfirmationFlowController - handles inline confirmation UI and resuming."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openhands.sdk.security.confirmation_policy import ConfirmRisky, NeverConfirm
from openhands_cli.user_actions.types import UserConfirmation


if TYPE_CHECKING:
    from collections.abc import Callable

    from openhands_cli.tui.core.confirmation_policy_service import (
        ConfirmationPolicyService,
    )
    from openhands_cli.tui.core.runner_registry import RunnerRegistry
    from openhands_cli.tui.core.state import ConversationContainer


class ConfirmationFlowController:
    def __init__(
        self,
        *,
        state: ConversationContainer,
        runners: RunnerRegistry,
        policy_service: ConfirmationPolicyService,
        run_worker: Callable[..., object],
    ) -> None:
        self._state = state
        self._runners = runners
        self._policy_service = policy_service
        self._run_worker = run_worker

    def show_panel(self, pending_action_count: int) -> None:
        self._state.set_pending_action_count(pending_action_count)

    def handle_decision(self, decision: UserConfirmation) -> None:
        self._state.set_pending_action_count(0)

        runner = self._runners.current
        if runner is None:
            return

        if decision == UserConfirmation.ALWAYS_PROCEED:
            self._policy_service.set_policy(NeverConfirm())
        elif decision == UserConfirmation.CONFIRM_RISKY:
            self._policy_service.set_policy(ConfirmRisky())

        self._run_worker(
            runner.resume_after_confirmation(decision),
            name="resume_conversation",
        )
