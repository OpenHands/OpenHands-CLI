# tests/tui/modals/settings/test_choices.py
"""Tests for settings choices module."""

from openhands.sdk.llm import OPENAI_CODEX_MODELS
from openhands_cli.tui.modals.settings.choices import (
    CHATGPT_PROVIDER_ID,
    CHATGPT_PROVIDER_LABEL,
    get_chatgpt_model_options,
    get_model_options,
    get_provider_options,
    is_chatgpt_provider,
)


def test_chatgpt_provider_in_options():
    """ChatGPT Subscription should be the first provider option."""
    options = get_provider_options()
    assert len(options) > 0
    # First option should be ChatGPT Subscription
    assert options[0] == (CHATGPT_PROVIDER_LABEL, CHATGPT_PROVIDER_ID)


def test_get_chatgpt_model_options():
    """get_chatgpt_model_options should return all Codex models."""
    options = get_chatgpt_model_options()
    model_values = [opt[1] for opt in options]

    # All Codex models should be in the options
    for model in OPENAI_CODEX_MODELS:
        assert model in model_values


def test_get_model_options_for_chatgpt_provider():
    """get_model_options should return Codex models for ChatGPT provider."""
    options = get_model_options(CHATGPT_PROVIDER_ID)
    model_values = [opt[1] for opt in options]

    # Should return Codex models
    assert len(model_values) == len(OPENAI_CODEX_MODELS)
    for model in OPENAI_CODEX_MODELS:
        assert model in model_values


def test_get_model_options_for_regular_provider():
    """get_model_options should return regular models for non-ChatGPT providers."""
    options = get_model_options("openai")
    model_values = [opt[1] for opt in options]

    # Should return some OpenAI models
    assert len(model_values) > 0
    # Should NOT be the Codex models (different set)
    assert set(model_values) != set(OPENAI_CODEX_MODELS)


def test_is_chatgpt_provider():
    """is_chatgpt_provider should correctly identify ChatGPT provider."""
    assert is_chatgpt_provider(CHATGPT_PROVIDER_ID) is True
    assert is_chatgpt_provider("openai") is False
    assert is_chatgpt_provider("anthropic") is False
    assert is_chatgpt_provider(None) is False
    assert is_chatgpt_provider("") is False
