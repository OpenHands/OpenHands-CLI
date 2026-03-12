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
        """Set the confirmation policy and persist it to settings.

        Args:
            policy: The confirmation policy to set
        """
        runner = self._runners.current
        if runner is not None and runner.conversation is not None:
            runner.conversation.set_confirmation_policy(policy)
        self._state.confirmation_policy = policy

        # Persist the policy to settings for future sessions
        from openhands_cli.stores import CliSettings

        cli_settings = CliSettings.load()
        cli_settings.default_confirmation_policy = CliSettings.policy_to_string(policy)
        cli_settings.save()
