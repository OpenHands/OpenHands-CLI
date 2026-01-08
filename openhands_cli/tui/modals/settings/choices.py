from openhands.sdk.llm import UNVERIFIED_MODELS_EXCLUDING_BEDROCK, VERIFIED_MODELS


def get_provider_options() -> list[tuple[str, str]]:
    """Get list of available LLM providers."""
    providers = list(VERIFIED_MODELS.keys()) + list(
        UNVERIFIED_MODELS_EXCLUDING_BEDROCK.keys()
    )
    return [(provider, provider) for provider in providers]


def get_model_options(provider: str) -> list[tuple[str, str]]:
    """Get list of available models for a provider."""
    models = VERIFIED_MODELS.get(
        provider, []
    ) + UNVERIFIED_MODELS_EXCLUDING_BEDROCK.get(provider, [])
    return [(model, model) for model in models]


provider_options = get_provider_options()
