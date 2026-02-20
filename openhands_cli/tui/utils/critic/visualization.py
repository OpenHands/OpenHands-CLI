"""Critic visualization utilities for TUI.

This module provides CLI-specific visualization for critic results.
It uses the SDK's star rating format but filters out some sections
that are less useful for CLI users (Likely Follow-up, Other).
"""

from typing import Any

from rich.text import Text

from openhands.sdk.critic.result import CriticResult
from openhands_cli.tui.widgets.collapsible import Collapsible


def create_critic_collapsible(critic_result: CriticResult) -> Collapsible:
    """Create a collapsible widget for critic score visualization.

    Args:
        critic_result: The critic result to visualize

    Returns:
        A Collapsible widget showing critic score with star rating
        and potential issues (filtered for CLI)
    """
    # Build title with star rating
    title_text = _build_critic_title(critic_result)

    # Build content with filtered categories (no follow-up, no other)
    content_text = _build_critic_content(critic_result)

    # Check if there's any content to display
    has_content = len(content_text.plain.strip()) > 0

    # Create collapsible - only expand if there's content to show
    collapsible = Collapsible(
        content_text,
        title=title_text,
        collapsed=not has_content,  # Collapse if no content
    )

    # Reduce padding for more compact display
    collapsible.styles.padding = (0, 0, 0, 1)  # top, right, bottom, left

    return collapsible


def _get_star_rating(score: float) -> str:
    """Convert score (0-1) to a 5-star rating string."""
    filled_stars = round(score * 5)
    empty_stars = 5 - filled_stars
    return "★" * filled_stars + "☆" * empty_stars


def _get_star_style(score: float) -> str:
    """Get the style for the star rating based on score."""
    if score >= 0.6:
        return "green"
    elif score >= 0.4:
        return "yellow"
    else:
        return "red"


def _build_critic_title(critic_result: CriticResult) -> Text:
    """Build a colored Rich Text title with star rating.

    Args:
        critic_result: The critic result to visualize

    Returns:
        Rich Text object with star rating and percentage
    """
    title = Text()

    # Add "Critic: agent success likelihood" label
    title.append("Critic: agent success likelihood ", style="bold")

    # Add star rating with color
    stars = _get_star_rating(critic_result.score)
    style = _get_star_style(critic_result.score)
    percentage = critic_result.score * 100
    title.append(stars, style=style)
    title.append(f" ({percentage:.1f}%)", style="dim")

    return title


def _build_critic_content(critic_result: CriticResult) -> Text:
    """Build the Rich Text content for critic score breakdown.

    For CLI, we only show Potential Issues and Infrastructure.
    We filter out Likely Follow-up and Other sections.

    Args:
        critic_result: The critic result to visualize

    Returns:
        Rich Text object with formatted critic breakdown
    """
    content_text = Text()

    # Use pre-categorized features from metadata if available
    if critic_result.metadata:
        categorized = critic_result.metadata.get("categorized_features")
        if categorized:
            _append_categorized_features_for_cli(content_text, categorized)
            return content_text

    # Fallback: display message as-is if no categorized features
    if critic_result.message:
        content_text.append(f"\n{critic_result.message}\n")

    return content_text


def _append_categorized_features_for_cli(
    content_text: Text, categorized: dict[str, Any]
) -> None:
    """Append features from pre-categorized metadata (CLI-filtered).

    Only shows Potential Issues and Infrastructure.
    Filters out Likely Follow-up and Other sections for CLI.

    Args:
        content_text: Rich Text object to append to
        categorized: Pre-categorized features from SDK metadata
    """
    has_content = False

    # Agent behavioral issues (Potential Issues)
    agent_issues = categorized.get("agent_behavioral_issues", [])
    if agent_issues:
        content_text.append("Potential Issues: ", style="bold")
        _append_feature_list_inline(content_text, agent_issues)
        has_content = True

    # Infrastructure issues
    infra_issues = categorized.get("infrastructure_issues", [])
    if infra_issues:
        if has_content:
            content_text.append("\n")
        content_text.append("Infrastructure: ", style="bold")
        _append_feature_list_inline(content_text, infra_issues)

    # NOTE: Likely Follow-up and Other sections are intentionally
    # NOT displayed in CLI as they are less actionable for users


def _append_feature_list_inline(
    content_text: Text,
    features: list[dict[str, Any]],
) -> None:
    """Append features inline with likelihood percentages.

    Args:
        content_text: Rich Text object to append to
        features: List of feature dicts with 'display_name' and 'probability'
    """
    for i, feature in enumerate(features):
        display_name = feature.get("display_name", feature.get("name", "Unknown"))
        prob = feature.get("probability", 0.0)
        percentage = prob * 100

        # Determine color based on probability
        if prob >= 0.7:
            prob_style = "red bold"
        elif prob >= 0.5:
            prob_style = "yellow"
        else:
            prob_style = "dim"

        # Add dot separator between features
        if i > 0:
            content_text.append(" · ", style="dim")

        content_text.append(f"{display_name}", style="white")
        content_text.append(f" (likelihood {percentage:.0f}%)", style=prob_style)
