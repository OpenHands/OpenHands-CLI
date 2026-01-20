"""Critic visualization utilities for TUI."""

import json
import math

from rich.text import Text

from openhands.sdk.critic.result import CriticResult
from openhands_cli.tui.utils.critic.taxonomy import FEATURE_CATEGORIES
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

    # Add predicted sentiment if available
    sentiment_str = _extract_predicted_sentiment(critic_result.message)
    if sentiment_str:
        title.append(" | ", style="dim")
        title.append("Predicted Sentiment: ", style="bold")

        # Color sentiment based on type
        if "Positive" in sentiment_str:
            sentiment_style = "green"
        elif "Negative" in sentiment_str:
            sentiment_style = "red"
        else:  # Neutral
            sentiment_style = "yellow"

        title.append(sentiment_str, style=sentiment_style)

    return title


def _extract_predicted_sentiment(message: str | None) -> str | None:
    """Extract the predicted sentiment with highest probability from critic message.

    Args:
        message: Critic result message containing JSON probabilities

    Returns:
        Formatted sentiment string like "Neutral (0.77)" or None if not found
    """
    if not message:
        return None

    try:
        start_idx = message.find("{")
        if start_idx == -1:
            return None

        probs_dict = json.loads(message[start_idx:])
        if not isinstance(probs_dict, dict):
            return None

        # Extract sentiment probabilities
        raw_probs = {
            "Positive": probs_dict.get("sentiment_positive", 0.0),
            "Negative": probs_dict.get("sentiment_negative", 0.0),
            "Neutral": probs_dict.get("sentiment_neutral", 0.0),
        }

        # Check if we have any probabilities
        if not any(raw_probs.values()):
            return None

        # Apply softmax normalization
        probs_list = list(raw_probs.values())
        exp_probs = [math.exp(p) for p in probs_list]
        exp_sum = sum(exp_probs)
        normalized_probs = [exp_p / exp_sum for exp_p in exp_probs]

        # Map normalized probabilities back to sentiment names
        sentiments = dict(zip(raw_probs.keys(), normalized_probs))

        # Find highest probability sentiment
        max_sentiment = max(sentiments.items(), key=lambda x: x[1])
        sentiment_name, prob = max_sentiment

        return f"{sentiment_name} ({prob:.2f})"
    except (json.JSONDecodeError, ValueError, KeyError):
        return None


def _build_critic_content(critic_result: CriticResult) -> Text:
    """Build the Rich Text content for critic score breakdown.

    Args:
        critic_result: The critic result to visualize

    Returns:
        Rich Text object with formatted critic breakdown
    """
    content_text = Text()

    # Parse and display detailed probabilities if available
    if critic_result.message:
        try:
            start_idx = critic_result.message.find("{")
            probs_dict = json.loads(critic_result.message[start_idx:])
            if isinstance(probs_dict, dict):
                _append_categorized_features(content_text, probs_dict)
            else:
                # If not a dict, display message as-is
                content_text.append(f"\n{critic_result.message}\n")
        except (json.JSONDecodeError, ValueError):
            # If parsing fails, display message as-is
            if critic_result.message:
                content_text.append(f"\n{critic_result.message}\n")

    return content_text


def _append_categorized_features(content_text: Text, probs_dict: dict) -> None:
    """Append features grouped by taxonomy categories.

    Args:
        content_text: Rich Text object to append to
        probs_dict: Dictionary of feature probabilities
    """
    # Group features by taxonomy categories
    agent_issues = {}
    user_patterns = {}
    infra_issues = {}
    unknown_features = {}

    for feature_name, prob in probs_dict.items():
        # Skip 'success' as it's redundant with the score
        if feature_name == "success":
            continue

        # Skip sentiment features as they're shown in the title
        if feature_name.startswith("sentiment_"):
            continue

        # Skip general context features (only user_goal_summary would appear here)
        # Sentiment is already in title, no need for this category
        category = FEATURE_CATEGORIES.get(feature_name)
        if category == "general_context":
            continue
        elif category == "agent_behavioral_issues":
            agent_issues[feature_name] = prob
        elif category == "user_followup_patterns":
            user_patterns[feature_name] = prob
        elif category == "infrastructure_issues":
            infra_issues[feature_name] = prob
        else:
            unknown_features[feature_name] = prob

    # Display each category if it has features
    if agent_issues:
        _append_category_section(
            content_text,
            "Detected Agent Behavioral Issues",
            agent_issues,
            "bold red",
            "agent",
        )

    if user_patterns:
        _append_category_section(
            content_text,
            "Predicted User Follow-Up Patterns",
            user_patterns,
            "bold magenta",
            "user",
        )

    if infra_issues:
        _append_category_section(
            content_text,
            "Detected Infrastructure Issues",
            infra_issues,
            "bold yellow",
            "infra",
        )

    if unknown_features:
        _append_category_section(
            content_text, "Other Metrics", unknown_features, "bold dim", "unknown"
        )


def _append_category_section(
    content_text: Text,
    title: str,
    features: dict,
    title_style: str,
    category: str,
) -> None:
    """Append a category section with features.

    Args:
        content_text: Rich Text object to append to
        title: Section title
        features: Dictionary of feature probabilities
        title_style: Rich style for the title
        category: Category type for color coding
    """
    content_text.append(f"{title}:\n", style=title_style)
    sorted_features = sorted(features.items(), key=lambda x: x[1], reverse=True)
    for feature, prob in sorted_features:
        _append_feature_with_prob(content_text, feature, prob, category)
    content_text.append("\n")


def _append_feature_with_prob(
    content_text: Text, feature_name: str, prob: float, category: str
) -> None:
    """Append a feature with its probability to the content text.

    Args:
        content_text: Rich Text object to append to
        feature_name: Name of the feature
        prob: Probability value
        category: Category type for color coding
    """
    # Format feature name: replace underscores with spaces, capitalize
    display_name = feature_name.replace("_", " ").title()

    # Determine color based on probability and category
    if category in ("agent", "user", "infra"):
        # Issue/prediction indicators (higher probability = more likely)
        if prob >= 0.7:
            prob_style = "red bold"
        elif prob >= 0.5:
            prob_style = "red"
        elif prob >= 0.3:
            prob_style = "yellow"
        else:
            prob_style = "dim"
    else:
        # Unknown category
        prob_style = "white"

    content_text.append(f"  • {display_name}: ", style="dim")
    content_text.append(f"{prob:.2f}\n", style=prob_style)
