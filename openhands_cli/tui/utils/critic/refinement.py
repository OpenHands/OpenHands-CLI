"""Iterative refinement utilities for critic-based agent improvement.

This module provides the follow-up prompt logic for iterative refinement,
following the pattern established in the OpenHands SDK:
https://docs.openhands.dev/sdk/guides/critic#iterative-refinement-with-a-critic
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from openhands.sdk.critic.result import CriticResult


def build_refinement_message(
    critic_result: CriticResult,
    threshold: float,  # noqa: ARG001 - kept for API compatibility
    iteration: int = 1,
    max_iterations: int = 3,
) -> str:
    """Build a follow-up message to send to the agent when critic score is low.

    This follows the SDK's iterative refinement pattern
    (see CriticBase.get_followup_prompt), providing a concise message that
    prompts the agent to review and improve its work.

    Args:
        critic_result: The critic result with score and metadata
        threshold: The threshold below which refinement is triggered
            (unused, kept for API compatibility)
        iteration: Current refinement iteration (1-indexed)
        max_iterations: Maximum number of refinement iterations allowed

    Returns:
        A formatted message string to send to the agent
    """
    score_percent = critic_result.score * 100

    # Use the same prompt format as the SDK's CriticBase.get_followup_prompt
    return (
        f"The task appears incomplete (iteration {iteration}/{max_iterations}, "
        f"predicted success likelihood: {score_percent:.1f}%).\n\n"
        "Please review what you've done and verify each requirement is met.\n"
        "List what's working and what needs fixing, then complete the task.\n"
    )


def should_trigger_refinement(
    critic_result: CriticResult | None,
    threshold: float,
    *,
    enabled: bool = True,
) -> bool:
    """Check if iterative refinement should be triggered.

    Args:
        critic_result: The critic result (may be None if critic is disabled)
        threshold: The threshold below which refinement is triggered
        enabled: Whether iterative refinement is enabled

    Returns:
        True if refinement should be triggered, False otherwise
    """
    if not enabled:
        return False

    if critic_result is None:
        return False

    return critic_result.score < threshold
