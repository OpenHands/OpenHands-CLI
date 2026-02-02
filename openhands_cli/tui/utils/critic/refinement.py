"""Iterative refinement utilities for critic-based agent improvement."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from openhands.sdk.critic.result import CriticResult


def build_refinement_message(
    critic_result: CriticResult,
    threshold: float,
) -> str:
    """Build a refinement message to send to the agent when critic score is low.

    Args:
        critic_result: The critic result with score and metadata
        threshold: The threshold below which refinement is triggered

    Returns:
        A formatted message string to send to the agent
    """
    score_percentage = critic_result.score * 100
    threshold_percentage = threshold * 100

    # Build the base message
    lines = [
        "⚠️ **Iterative Refinement Triggered**",
        "",
        f"The critic model has predicted that your task success probability "
        f"is **{score_percentage:.1f}%**, which is below the threshold of "
        f"{threshold_percentage:.0f}%.",
        "",
    ]

    # Add detailed breakdown if categorized features are available
    if critic_result.metadata and "categorized_features" in critic_result.metadata:
        categorized = critic_result.metadata["categorized_features"]
        rubric_details = _format_rubric_details(categorized)
        if rubric_details:
            lines.append("**Detailed probability breakdown:**")
            lines.append("")
            lines.extend(rubric_details)
            lines.append("")

    # Add the refinement instruction
    lines.extend(
        [
            "**Please review the user's original requirements and your current "
            "changes.**",
            "",
            "Ensure you have:",
            "1. Fully addressed all aspects of the user's request",
            "2. Verified your implementation is complete and correct",
            "3. Resolved any potential issues identified above",
            "",
            "If you believe the task is complete, use the finish tool to explain "
            "what was accomplished. Otherwise, continue working on the remaining "
            "items.",
        ]
    )

    return "\n".join(lines)


def _format_rubric_details(categorized: dict) -> list[str]:
    """Format categorized features into readable rubric details.

    Args:
        categorized: Dict containing categorized features from critic metadata

    Returns:
        List of formatted detail lines
    """
    details = []

    # Agent behavioral issues
    agent_issues = categorized.get("agent_behavioral_issues", [])
    if agent_issues:
        details.append("- **Potential Issues:**")
        for feature in agent_issues:
            name = feature.get("display_name", feature.get("name", "Unknown"))
            prob = feature.get("probability", 0.0)
            details.append(f"  - {name}: {prob * 100:.0f}% likelihood")

    # Infrastructure issues
    infra_issues = categorized.get("infrastructure_issues", [])
    if infra_issues:
        details.append("- **Infrastructure:**")
        for feature in infra_issues:
            name = feature.get("display_name", feature.get("name", "Unknown"))
            prob = feature.get("probability", 0.0)
            details.append(f"  - {name}: {prob * 100:.0f}% likelihood")

    # User follow-up patterns (might indicate incomplete work)
    user_patterns = categorized.get("user_followup_patterns", [])
    if user_patterns:
        details.append("- **Likely Follow-up Needed:**")
        for feature in user_patterns:
            name = feature.get("display_name", feature.get("name", "Unknown"))
            prob = feature.get("probability", 0.0)
            details.append(f"  - {name}: {prob * 100:.0f}% likelihood")

    return details


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
