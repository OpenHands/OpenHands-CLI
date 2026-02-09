import litellm

from openhands.sdk.llm import (
    OPENAI_CODEX_MODELS,
    UNVERIFIED_MODELS_EXCLUDING_BEDROCK,
    VERIFIED_MODELS,
)


# Special provider ID for ChatGPT subscription auth
CHATGPT_PROVIDER_ID = "chatgpt-subscription"
CHATGPT_PROVIDER_LABEL = "ChatGPT Subscription"

# Get set of valid litellm provider names for filtering
# See: https://docs.litellm.ai/docs/providers
_VALID_LITELLM_PROVIDERS: set[str] = {
    str(getattr(p, "value", p)) for p in litellm.provider_list
}


def get_provider_options() -> list[tuple[str, str]]:
    """Get list of available LLM providers.

    Includes:
    - ChatGPT Subscription (special provider for OAuth-based auth)
    - All VERIFIED_MODELS providers (openhands, openai, anthropic, mistral)
      even if not in litellm.provider_list (e.g. 'openhands' is custom)
    - UNVERIFIED providers that are known to litellm (filters out invalid
      "providers" like 'meta-llama', 'Qwen' which are vendor names)

    Sorted alphabetically, with ChatGPT Subscription at the top.
    """
    # Verified providers always included (includes custom like 'openhands')
    verified_providers = set(VERIFIED_MODELS.keys())

    # Unverified providers are filtered to only valid litellm providers
    unverified_providers = set(UNVERIFIED_MODELS_EXCLUDING_BEDROCK.keys())
    valid_unverified = unverified_providers & _VALID_LITELLM_PROVIDERS

    # Combine and sort
    all_valid_providers = sorted(verified_providers | valid_unverified)

    # Build options list with ChatGPT Subscription at the top
    options: list[tuple[str, str]] = [
        (CHATGPT_PROVIDER_LABEL, CHATGPT_PROVIDER_ID),
    ]
    options.extend((provider, provider) for provider in all_valid_providers)

    return options


def get_model_options(provider: str) -> list[tuple[str, str]]:
    """Get list of available models for a provider, sorted alphabetically."""
    # Special handling for ChatGPT subscription
    if provider == CHATGPT_PROVIDER_ID:
        return get_chatgpt_model_options()

    models = VERIFIED_MODELS.get(
        provider, []
    ) + UNVERIFIED_MODELS_EXCLUDING_BEDROCK.get(provider, [])

    # Remove duplicates and sort
    unique_models = sorted(set(models))

    return [(model, model) for model in unique_models]


def get_chatgpt_model_options() -> list[tuple[str, str]]:
    """Get list of available ChatGPT subscription models."""
    models = sorted(OPENAI_CODEX_MODELS)
    return [(model, model) for model in models]


def is_chatgpt_provider(provider: str | None) -> bool:
    """Check if the given provider is the ChatGPT subscription provider."""
    return provider == CHATGPT_PROVIDER_ID


provider_options = get_provider_options()
