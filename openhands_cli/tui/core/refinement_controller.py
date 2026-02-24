"""RefinementController - handles iterative refinement based on critic results.

This controller encapsulates the iterative refinement logic:
1. Receives critic results when the agent completes a message
2. Evaluates whether refinement should be triggered
3. Sends refinement messages to the agent when needed
4. Tracks iteration count to prevent infinite loops

The refinement iteration counter resets when the user sends a new message,
allowing refinement to continue within a single user turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openhands_cli.tui.messages import SendRefinementMessage
from openhands_cli.tui.utils.critic.refinement import (
    build_refinement_message,
    should_trigger_refinement,
)


if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from openhands.sdk.critic.result import CriticResult
    from openhands_cli.tui.core.runner_registry import RunnerRegistry
    from openhands_cli.tui.core.state import ConversationContainer


class RefinementController:
    """Controller for iterative refinement based on critic evaluation.

    This controller owns the refinement business logic, keeping it separate
    from the visualizer (presentation) and state container (reactive state).

    Responsibilities:
    - Evaluate critic results and decide whether to trigger refinement
    - Build and send refinement messages
    - Track iteration count within a user turn

    The iteration counter is stored in ConversationContainer for thread-safe
    access and proper reset when the user sends a new message.
    """

    def __init__(
        self,
        *,
        state: ConversationContainer,
        runners: RunnerRegistry,
        post_message: Callable[..., Any],
    ) -> None:
        """Initialize the refinement controller.

        Args:
            state: The conversation state container (owns refinement_iteration)
            runners: Registry of conversation runners
            post_message: Function to post Textual messages
        """
        self._state = state
        self._runners = runners
        self._post_message = post_message

    def handle_critic_result(self, critic_result: CriticResult) -> None:
        """Handle a critic result and trigger refinement if needed.

        This is the main entry point called when a critic result is received.
        It evaluates the result against the current settings and triggers
        refinement by posting a SendRefinementMessage if conditions are met.

        Args:
            critic_result: The critic evaluation result to handle.
        """
        critic_settings = self._state.critic_settings

        if not critic_settings.enable_iterative_refinement:
            return

        max_iterations = critic_settings.max_refinement_iterations
        current_iteration = self._state.refinement_iteration

        if current_iteration >= max_iterations:
            return

        should_refine, triggered_issues = should_trigger_refinement(
            critic_result=critic_result,
            threshold=critic_settings.critic_threshold,
            issue_threshold=critic_settings.issue_threshold,
        )

        if not should_refine:
            return

        # Increment iteration count
        new_iteration = current_iteration + 1
        self._state.set_refinement_iteration(new_iteration)

        # Build and send refinement message
        refinement_message = build_refinement_message(
            critic_result=critic_result,
            iteration=new_iteration,
            max_iterations=max_iterations,
            issue_threshold=critic_settings.issue_threshold,
            triggered_issues=triggered_issues,
        )

        self._post_message(SendRefinementMessage(refinement_message))

    def reset_iteration(self) -> None:
        """Reset the refinement iteration counter.

        Called when the user sends a new message (starting a new user turn).
        """
        self._state.set_refinement_iteration(0)
