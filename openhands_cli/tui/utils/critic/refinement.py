"""Iterative refinement helpers used by the CLI critic flow."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from openhands.sdk.critic.result import CriticResult


@dataclass(frozen=True)
class RefinementDecision:
    """Result of evaluating whether iterative refinement should run."""

    should_refine: bool
    triggered_issues: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class CliIterativeRefinementConfig:
    """Runtime configuration for CLI iterative refinement."""

    success_threshold: float
    max_iterations: int
    issue_threshold: float = 0.75

    def evaluate(self, critic_result: CriticResult | None) -> RefinementDecision:
        return evaluate_iterative_refinement(
            critic_result,
            success_threshold=self.success_threshold,
            issue_threshold=self.issue_threshold,
        )

    def build_followup_prompt(
        self,
        critic_result: CriticResult,
        iteration: int,
        *,
        decision: RefinementDecision | None = None,
    ) -> str:
        return build_refinement_message(
            critic_result,
            iteration=iteration,
            max_iterations=self.max_iterations,
            issue_threshold=self.issue_threshold,
            triggered_issues=(list(decision.triggered_issues) if decision else None),
        )


def _format_feature_for_prompt(feature: dict[str, Any]) -> str:
    name = feature.get("display_name", feature.get("name", "Unknown"))
    probability = feature.get("probability", 0)
    return f"{name} ({probability:.0%})"


def get_high_probability_issues(
    critic_result: CriticResult,
    issue_threshold: float,
) -> list[dict[str, Any]]:
    if not critic_result.metadata:
        return []

    categorized = critic_result.metadata.get("categorized_features", {})
    if not categorized:
        return []

    issues = [
        issue
        for issue in categorized.get("agent_behavioral_issues", [])
        if issue.get("probability", 0) >= issue_threshold
    ]
    issues.sort(key=lambda issue: issue.get("probability", 0), reverse=True)
    return issues


def evaluate_iterative_refinement(
    critic_result: CriticResult | None,
    success_threshold: float,
    *,
    issue_threshold: float = 0.75,
) -> RefinementDecision:
    if critic_result is None:
        return RefinementDecision(should_refine=False)

    triggered_issues = tuple(
        get_high_probability_issues(critic_result, issue_threshold=issue_threshold)
    )
    should_refine = critic_result.score < success_threshold or bool(triggered_issues)
    return RefinementDecision(
        should_refine=should_refine,
        triggered_issues=triggered_issues,
    )


def build_refinement_message(
    critic_result: CriticResult,
    iteration: int = 1,
    max_iterations: int = 3,
    *,
    issue_threshold: float = 0.75,
    triggered_issues: Sequence[dict[str, Any]] | None = None,
) -> str:
    score_percent = critic_result.score * 100
    lines = [
        (
            f"The task appears incomplete (iteration {iteration}/{max_iterations}, "
            f"predicted success likelihood: {score_percent:.1f}%)."
        ),
        "",
    ]

    if triggered_issues is None:
        triggered_issues = get_high_probability_issues(
            critic_result,
            issue_threshold=issue_threshold,
        )

    if triggered_issues:
        lines.append("**Detected issues requiring attention:**")
        for issue in triggered_issues:
            lines.append(f"- {_format_feature_for_prompt(issue)}")
        lines.append("")

    lines.extend(
        [
            "Please review what you've done and verify each requirement is met.",
            "List what's working and what needs fixing, then complete the task.",
        ]
    )
    return "\n".join(lines)
