"""Critic visualization utilities for TUI."""

from typing import Any

from rich.text import Text

from openhands.sdk.critic.result import CriticResult
from openhands_cli.tui.widgets.collapsible import Collapsible


def create_critic_collapsible(critic_result: CriticResult) -> Collapsible:
    """Create a collapsible widget for critic score visualization.

    Args:
        critic_result: The critic result to visualize

    Returns:
        A Collapsible widget showing critic score summary (collapsed)
        and full breakdown (expanded), organized by taxonomy categories
    """
    # Build title with colored score and predicted sentiment
    title_text = _build_critic_title(critic_result)

    # Build content with category grouping
    content_text = _build_critic_content(critic_result)

    # Create collapsible (start expanded by default)
    collapsible = Collapsible(
        content_text,
        title=title_text,
        collapsed=False,
        border_color="#888888",  # Default gray border
    )

    # Reduce padding for more compact display
    collapsible.styles.padding = (0, 0, 0, 1)  # top, right, bottom, left

    return collapsible


def _build_critic_title(critic_result: CriticResult) -> Text:
    """Build a colored Rich Text title for the critic collapsible.

    Args:
        critic_result: The critic result to visualize

    Returns:
        Rich Text object with colored score and sentiment
    """
    title = Text()

    # Add "Critic Score:" label
    title.append("Critic Score: ", style="bold")

    # Add colored score
    score_style = "green bold" if critic_result.success else "yellow bold"
    title.append(f"{critic_result.score:.4f}", style=score_style)
    title.append(" (0-1, higher is better)", style="dim")

    # Add predicted sentiment if available from metadata
    sentiment = _get_sentiment_from_metadata(critic_result)
    if sentiment:
        title.append(" | ", style="dim")
        title.append("Predicted User Sentiment: ", style="bold")

        # Color sentiment based on type
        predicted = sentiment.get("predicted", "")
        if predicted == "Positive":
            sentiment_style = "green"
        elif predicted == "Negative":
            sentiment_style = "red"
        else:  # Neutral
            sentiment_style = "yellow"

        prob = sentiment.get("probability", 0.0)
        title.append(f"{predicted} ({prob:.2f})", style=sentiment_style)

    return title


def _get_sentiment_from_metadata(critic_result: CriticResult) -> dict[str, Any] | None:
    """Extract sentiment from critic result metadata.

    Args:
        critic_result: The critic result

    Returns:
        Sentiment dict with 'predicted' and 'probability' keys, or None
    """
    if not critic_result.metadata:
        return None

    categorized = critic_result.metadata.get("categorized_features")
    if not categorized:
        return None

    return categorized.get("sentiment")


def _build_critic_content(critic_result: CriticResult) -> Text:
    """Build the Rich Text content for critic score breakdown.

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
            _append_categorized_features_from_metadata(content_text, categorized)
            return content_text

    # Fallback: display message as-is if no categorized features
    if critic_result.message:
        content_text.append(f"\n{critic_result.message}\n")

    return content_text


def _append_categorized_features_from_metadata(
    content_text: Text, categorized: dict[str, Any]
) -> None:
    """Append features from pre-categorized metadata.

    Args:
        content_text: Rich Text object to append to
        categorized: Pre-categorized features from SDK metadata
    """
    has_content = False

    # Agent behavioral issues
    agent_issues = categorized.get("agent_behavioral_issues", [])
    if agent_issues:
        content_text.append("Detected Agent Issues: ", style="bold")
        _append_feature_list_inline(content_text, agent_issues)
        has_content = True

    # User follow-up patterns
    user_patterns = categorized.get("user_followup_patterns", [])
    if user_patterns:
        if has_content:
            content_text.append("\n")
        content_text.append("Predicted User Follow-Up: ", style="bold")
        _append_feature_list_inline(content_text, user_patterns)
        has_content = True

    # Infrastructure issues
    infra_issues = categorized.get("infrastructure_issues", [])
    if infra_issues:
        if has_content:
            content_text.append("\n")
        content_text.append("Infra Issues: ", style="bold")
        _append_feature_list_inline(content_text, infra_issues)
        has_content = True

    # Other metrics
    other = categorized.get("other", [])
    if other:
        if has_content:
            content_text.append("\n")
        content_text.append("Other: ", style="bold dim")
        _append_feature_list_inline(content_text, other, is_other=True)


def _append_feature_list_inline(
    content_text: Text,
    features: list[dict[str, Any]],
    is_other: bool = False,
) -> None:
    """Append features inline with dot separators.

    Args:
        content_text: Rich Text object to append to
        features: List of feature dicts with 'display_name' and 'probability'
        is_other: Whether this is the "other" category
    """
    for i, feature in enumerate(features):
        display_name = feature.get("display_name", feature.get("name", "Unknown"))
        prob = feature.get("probability", 0.0)

        # Determine color based on probability
        if is_other:
            prob_style = "white"
        elif prob >= 0.7:
            prob_style = "red bold"
        elif prob >= 0.5:
            prob_style = "red"
        elif prob >= 0.3:
            prob_style = "yellow"
        else:
            prob_style = "dim"

        # Add dot separator between features
        if i > 0:
            content_text.append(" · ", style="dim")

        content_text.append(f"{display_name} ", style="dim")
        content_text.append(f"({prob:.2f})", style=prob_style)
