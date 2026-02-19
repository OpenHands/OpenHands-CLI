"""Iterative refinement utilities for critic-based agent improvement.

This module provides the follow-up prompt logic for iterative refinement,
following the pattern established in the OpenHands SDK:
https://docs.openhands.dev/sdk/guides/critic#iterative-refinement-with-a-critic

Refinement can be triggered in two ways:
1. When the overall success score is below the critic threshold
2. When any specific issue (e.g., insufficient_testing) has a probability
   above the issue threshold, even if the overall score is acceptable
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from openhands.sdk.critic.result import CriticResult


def _format_feature_for_prompt(feature: dict[str, Any]) -> str:
    """Format a single feature for display in the refinement prompt.

    Args:
        feature: Feature dict with 'display_name' and 'probability'

    Returns:
        Formatted string like "Insufficient Testing (75%)"
    """
    name = feature.get("display_name", feature.get("name", "Unknown"))
    prob = feature.get("probability", 0)
    return f"{name} ({prob:.0%})"


def get_high_probability_issues(
    critic_result: CriticResult,
    issue_threshold: float,
) -> list[dict[str, Any]]:
    """Extract issues with probability above the threshold.

    Looks for agent behavioral issues and other detected issues from the
    critic's categorized features that have probability >= issue_threshold.

    Args:
        critic_result: The critic result with metadata
        issue_threshold: Minimum probability to consider an issue significant

    Returns:
        List of issue dicts with 'name', 'display_name', and 'probability'
    """
    if not critic_result.metadata:
        return []

    categorized = critic_result.metadata.get("categorized_features", {})
    if not categorized:
        return []

    high_prob_issues: list[dict[str, Any]] = []

    # Check agent behavioral issues (e.g., insufficient_testing, loop_behavior)
    for issue in categorized.get("agent_behavioral_issues", []):
        if issue.get("probability", 0) >= issue_threshold:
            high_prob_issues.append(issue)

    # Sort by probability (highest first)
    high_prob_issues.sort(key=lambda x: x.get("probability", 0), reverse=True)

    return high_prob_issues


def build_refinement_message(
    critic_result: CriticResult,
    iteration: int = 1,
    max_iterations: int = 3,
    *,
    issue_threshold: float = 0.75,
    triggered_issues: list[dict[str, Any]] | None = None,
) -> str:
    """Build a follow-up message to send to the agent when refinement is needed.

    This follows the SDK's iterative refinement pattern
    (see CriticBase.get_followup_prompt), providing a concise message that
    prompts the agent to review and improve its work.

    The message includes specific issues detected by the critic when available,
    helping the agent understand what needs attention.

    Args:
        critic_result: The critic result with score and metadata
        iteration: Current refinement iteration (1-indexed)
        max_iterations: Maximum number of refinement iterations allowed
        issue_threshold: Threshold for highlighting specific issues
        triggered_issues: Pre-computed list of issues that triggered refinement.
            If None, issues are extracted from critic_result.

    Returns:
        A formatted message string to send to the agent
    """
    score_percent = critic_result.score * 100

    lines = [
        f"The task appears incomplete (iteration {iteration}/{max_iterations}, "
        f"predicted success likelihood: {score_percent:.1f}%).",
        "",
    ]

    # Get issues that triggered refinement (or extract from metadata)
    if triggered_issues is None:
        triggered_issues = get_high_probability_issues(critic_result, issue_threshold)

    # Include specific issues if detected
    if triggered_issues:
        lines.append("**Detected issues requiring attention:**")
        for issue in triggered_issues:
            formatted = _format_feature_for_prompt(issue)
            lines.append(f"- {formatted}")
        lines.append("")

    lines.extend(
        [
            "Please review what you've done and verify each requirement is met.",
            "List what's working and what needs fixing, then complete the task.",
        ]
    )

    return "\n".join(lines)


def should_trigger_refinement(
    critic_result: CriticResult | None,
    threshold: float,
    *,
    issue_threshold: float = 0.75,
) -> tuple[bool, list[dict[str, Any]]]:
    """Check if iterative refinement should be triggered.

    Refinement is triggered when:
    1. The overall success score is below the threshold, OR
    2. Any specific issue has probability >= issue_threshold

    Args:
        critic_result: The critic result (may be None if critic is disabled)
        threshold: The overall score threshold below which refinement is triggered
        issue_threshold: Threshold for individual issue detection

    Returns:
        Tuple of (should_trigger, triggered_issues):
        - should_trigger: True if refinement should be triggered
        - triggered_issues: List of issues that triggered refinement (may be empty)
    """
    if critic_result is None:
        return False, []

    # Check for high-probability issues first
    high_prob_issues = get_high_probability_issues(critic_result, issue_threshold)

    # Trigger if overall score is low OR if specific issues detected
    if critic_result.score < threshold:
        return True, high_prob_issues

    if high_prob_issues:
        return True, high_prob_issues

    return False, []
