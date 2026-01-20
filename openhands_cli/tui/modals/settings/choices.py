import litellm

from openhands.sdk.llm import UNVERIFIED_MODELS_EXCLUDING_BEDROCK, VERIFIED_MODELS


# Get set of valid litellm provider names for filtering
# See: https://docs.litellm.ai/docs/providers
_VALID_LITELLM_PROVIDERS: set[str] = {
    str(getattr(p, "value", p)) for p in litellm.provider_list
}


def get_provider_options() -> list[tuple[str, str]]:
    """Get list of available LLM providers.

    Includes:
    - All VERIFIED_MODELS providers (openhands, openai, anthropic, mistral)
      even if not in litellm.provider_list (e.g. 'openhands' is custom)
    - UNVERIFIED providers that are known to litellm (filters out invalid
      "providers" like 'meta-llama', 'Qwen' which are vendor names)

    Sorted alphabetically.
    """
    # Verified providers always included (includes custom like 'openhands')
    verified_providers = set(VERIFIED_MODELS.keys())

    # Unverified providers are filtered to only valid litellm providers
    unverified_providers = set(UNVERIFIED_MODELS_EXCLUDING_BEDROCK.keys())
    valid_unverified = unverified_providers & _VALID_LITELLM_PROVIDERS

    # Combine and sort
    all_valid_providers = sorted(verified_providers | valid_unverified)

    return [(provider, provider) for provider in all_valid_providers]


def get_model_options(provider: str) -> list[tuple[str, str]]:
    """Get list of available models for a provider, sorted alphabetically."""
    models = VERIFIED_MODELS.get(
        provider, []
    ) + UNVERIFIED_MODELS_EXCLUDING_BEDROCK.get(provider, [])

    # Remove duplicates and sort
    unique_models = sorted(set(models))

    return [(model, model) for model in unique_models]


provider_options = get_provider_options()
