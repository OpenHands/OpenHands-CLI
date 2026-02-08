"""Model recommendations data for CLI settings.

This module contains recommended models and their use cases based on
OpenHands evaluations and community feedback. This data is easily
updateable and displayed in the CLI settings.

Source: https://docs.openhands.dev/openhands/usage/llms/llms#cloud-/-api-based-models
"""

from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, ConfigDict
from textual.widgets import Static


# UI Constants
RECOMMENDED_INDICATOR = " ⭐ (Recommended)"
USE_CASES_PREFIX = "Use cases: "
NOTE_PREFIX = "Note: "
BULLET_POINT = "• "

# Category Titles
CLOUD_CATEGORY_TITLE = "Cloud / API-Based Models"
LOCAL_CATEGORY_TITLE = "Local / Self-Hosted Models"


class ModelRecommendation(BaseModel):
    """Represents a model recommendation with its details.

    Attributes:
        name: The model name/identifier
        provider: The provider name (e.g., "anthropic", "openai")
        is_recommended: Whether this model is marked as recommended
        use_cases: Description of what tasks this model excels at
        notes: Additional notes or information about the model
    """

    model_config = ConfigDict(frozen=True)

    name: str
    provider: str
    is_recommended: bool = False
    use_cases: str | None = None
    notes: str | None = None

    def format_display_name(self) -> str:
        """Format the model name for display.

        Returns:
            Formatted string like "provider/model-name" with optional
            recommended indicator.
        """
        model_text = f"{BULLET_POINT}{self.provider}/{self.name}"
        if self.is_recommended:
            model_text += RECOMMENDED_INDICATOR
        return model_text


# Cloud / API-Based Models
CLOUD_MODELS: list[ModelRecommendation] = [
    ModelRecommendation(
        name="claude-opus-4-5-20251101",
        provider="anthropic",
        is_recommended=True,
        use_cases="Coding, agents, computer use, complex problem solving",
        notes=(
            "State-of-the-art on SWE-bench Verified. "
            "Best model for coding and agentic workflows"
        ),
    ),
    ModelRecommendation(
        name="claude-sonnet-4-5-20250929",
        provider="anthropic",
        is_recommended=True,
        use_cases="General coding tasks, complex problem solving",
        notes="Latest Claude Sonnet model with strong performance",
    ),
    ModelRecommendation(
        name="claude-sonnet-4-20250514",
        provider="anthropic",
        is_recommended=True,
        use_cases="General coding tasks, complex problem solving",
    ),
    ModelRecommendation(
        name="gpt-5-2025-08-07",
        provider="openai",
        is_recommended=True,
        use_cases="General coding tasks, code generation",
        notes="GPT-5.0 model with strong performance",
    ),
    ModelRecommendation(
        name="gemini-3-pro-preview",
        provider="gemini",
        use_cases="General coding tasks",
    ),
    ModelRecommendation(
        name="deepseek-chat",
        provider="deepseek",
        use_cases="Cost-effective coding tasks",
    ),
    ModelRecommendation(
        name="kimi-k2-0711-preview",
        provider="moonshot",
        use_cases="General coding tasks",
    ),
]

# Local / Self-Hosted Models
LOCAL_MODELS: list[ModelRecommendation] = [
    ModelRecommendation(
        name="devstral-small",
        provider="mistralai",
        is_recommended=True,
        use_cases="Local development, privacy-sensitive tasks",
        notes="Available from 20 May 2025, also available through OpenRouter",
    ),
    ModelRecommendation(
        name="openhands-lm-32b-v0.1",
        provider="all-hands",
        is_recommended=True,
        use_cases="Local development, privacy-sensitive tasks",
        notes="Available from 31 March 2025, also available through OpenRouter",
    ),
]


def render_model_recommendations() -> Iterator[Static]:
    """Render model recommendations as Static widgets.

    Yields:
        Static widgets for displaying model recommendations including
        section titles, model names, use cases, and notes.
    """
    recommendations = get_all_recommendations()

    # Render cloud/API-based models
    yield from _render_model_list(recommendations["cloud"], CLOUD_CATEGORY_TITLE)

    # Render local/self-hosted models
    yield from _render_model_list(recommendations["local"], LOCAL_CATEGORY_TITLE)


def get_all_recommendations() -> dict[
    Literal["cloud", "local"], list[ModelRecommendation]
]:
    """Get all model recommendations organized by type.

    Returns:
        Dictionary with "cloud" and "local" keys, each containing
        a list of ModelRecommendation objects.
    """
    return {
        "cloud": CLOUD_MODELS,
        "local": LOCAL_MODELS,
    }


def _render_model_list(
    models: list[ModelRecommendation], category_title: str
) -> Iterator[Static]:
    """Render a list of models as Static widgets.

    Args:
        models: List of model recommendations to render
        category_title: Title for the category section

    Yields:
        Static widgets for the category title and each model's details.
    """
    yield Static(category_title, classes="model_category_title")
    for model in models:
        yield Static(model.format_display_name(), classes="model_name")
        if model.use_cases:
            yield Static(
                f"{USE_CASES_PREFIX}{model.use_cases}", classes="model_details"
            )
        if model.notes:
            yield Static(f"{NOTE_PREFIX}{model.notes}", classes="model_details")
