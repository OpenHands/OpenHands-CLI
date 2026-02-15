from openhands.sdk.llm import UNVERIFIED_MODELS_EXCLUDING_BEDROCK, VERIFIED_MODELS


def get_provider_options() -> list[tuple[str, str]]:
    """Get list of available LLM providers.

    Includes:
    - All VERIFIED_MODELS providers
    - All UNVERIFIED_MODELS_EXCLUDING_BEDROCK providers

    Sorted alphabetically.
    """
    providers = sorted(
        set(VERIFIED_MODELS.keys()) | set(UNVERIFIED_MODELS_EXCLUDING_BEDROCK.keys())
    )
    return [(provider, provider) for provider in providers]


def get_model_options(provider: str) -> list[tuple[str, str]]:
    """Get list of available models for a provider.

    Models are returned in their original order (VERIFIED first, then UNVERIFIED),
    preserving the original casing. Duplicates are removed while maintaining order.
    """
    models = VERIFIED_MODELS.get(
        provider, []
    ) + UNVERIFIED_MODELS_EXCLUDING_BEDROCK.get(provider, [])

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_models: list[str] = []
    for model in models:
        if model not in seen:
            seen.add(model)
            unique_models.append(model)

    return [(model, model) for model in unique_models]


provider_options = get_provider_options()
