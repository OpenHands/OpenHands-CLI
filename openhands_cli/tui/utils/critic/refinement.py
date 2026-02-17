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
    threshold: float,
) -> str:
    """Build a follow-up message to send to the agent when critic score is low.

    This follows the SDK's iterative refinement pattern, providing a concise
    message that prompts the agent to review and improve its work.

    Args:
        critic_result: The critic result with score and metadata
        threshold: The threshold below which refinement is triggered

    Returns:
        A formatted message string to send to the agent
    """
    score_percent = critic_result.score * 100
    threshold_percent = threshold * 100

    # Build a concise follow-up message similar to the SDK's default pattern
    score_line = (
        f"Your solution scored {score_percent:.1f}% "
        f"(threshold: {threshold_percent:.0f}%)."
    )
    lines = [
        score_line,
        "",
        "Please review your work carefully:",
        "1. Check that all requirements from the original request are met",
        "2. Verify your implementation is complete and correct",
        "3. Fix any issues and try again",
    ]

    return "\n".join(lines)


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
