"""LLM model management utilities for ACP implementation."""

import logging

from acp.schema import ModelInfo

from openhands.sdk import BaseConversation
from openhands.sdk.llm import UNVERIFIED_MODELS_EXCLUDING_BEDROCK, VERIFIED_MODELS


logger = logging.getLogger(__name__)


def determine_provider(model: str, base_url: str | None) -> str | None:
    """Determine the provider from the model string and base URL.

    Args:
        model: The model identifier (e.g., "litellm_proxy/claude-sonnet-4-5-20250929")
        base_url: The base URL if using a custom endpoint

    Returns:
        Provider name (e.g., "openhands", "anthropic", "openai") or None if unknown
    """
    # Check if using OpenHands proxy
    if base_url and "all-hands.dev" in base_url:
        return "openhands"

    # Check if model has a provider prefix
    if "/" in model:
        provider_prefix = model.split("/")[0]
        # litellm_proxy is a special case - need to check the actual model
        if provider_prefix == "litellm_proxy":
            # Extract the actual model name after the prefix
            actual_model = model.split("/", 1)[1] if "/" in model else model
            # Try to match against known providers by checking if the model exists
            for provider, models in {
                **VERIFIED_MODELS,
                **UNVERIFIED_MODELS_EXCLUDING_BEDROCK,
            }.items():
                if actual_model in models:
                    return provider
            return None
        else:
            # Direct provider prefix like "anthropic/", "openai/"
            return provider_prefix

    # Try to match model name against provider model lists
    for provider, models in {
        **VERIFIED_MODELS,
        **UNVERIFIED_MODELS_EXCLUDING_BEDROCK,
    }.items():
        if model in models:
            return provider

    return None


def get_available_models(conversation: BaseConversation) -> list[ModelInfo]:
    """Get list of available models for the current provider using CLI's model registry.

    This reuses the same logic as the CLI settings screen, which uses VERIFIED_MODELS
    and UNVERIFIED_MODELS_EXCLUDING_BEDROCK to determine available models.

    Args:
        conversation: The conversation instance with LLM configuration

    Returns:
        List of ModelInfo objects representing available models from the same provider
    """
    try:
        llm = conversation.agent.llm  # type: ignore[attr-defined]
        current_model = llm.model
        base_url = llm.base_url

        # Determine the provider
        provider = determine_provider(current_model, base_url)

        if not provider:
            logger.debug(
                "Could not determine provider for model %s, "
                "returning current model only",
                current_model,
            )
            return [
                ModelInfo(
                    modelId=current_model,
                    name=current_model,
                    description=f"Current model: {current_model}",
                )
            ]

        # Get available models for this provider from the CLI's model registry
        available_model_ids = VERIFIED_MODELS.get(
            provider, []
        ) + UNVERIFIED_MODELS_EXCLUDING_BEDROCK.get(provider, [])

        if not available_model_ids:
            logger.debug(
                "No models found for provider %s, returning current model only",
                provider,
            )
            return [
                ModelInfo(
                    modelId=current_model,
                    name=current_model,
                    description=f"Current model: {current_model}",
                )
            ]

        # Convert to ModelInfo objects
        # Need to format the model ID based on current configuration
        available_models = []
        for model_id in available_model_ids:
            # Format the full model ID to match the current configuration
            if current_model.startswith("litellm_proxy/"):
                full_model_id = f"litellm_proxy/{model_id}"
            elif "/" in current_model and not current_model.startswith(
                "litellm_proxy/"
            ):
                # Has a provider prefix like "anthropic/"
                prefix = current_model.split("/")[0]
                full_model_id = f"{prefix}/{model_id}"
            else:
                # No prefix
                full_model_id = model_id

            available_models.append(
                ModelInfo(
                    modelId=full_model_id,
                    name=model_id,
                    description=f"{provider.capitalize()} model",
                )
            )

        logger.debug(
            "Found %d models for provider %s",
            len(available_models),
            provider,
        )
        return available_models

    except Exception as e:
        logger.error("Error getting available models: %s", e, exc_info=True)
        # Return empty list on error
        return []
