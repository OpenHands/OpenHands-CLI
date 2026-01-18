from openhands_cli.stores.agent_store import DEFAULT_LLM_BASE_URL, resolve_llm_base_url


def test_resolve_llm_base_url_prefers_explicit_value() -> None:
    settings = {"llm_base_url": "https://llm-proxy.eval.all-hands.dev/"}
    assert (
        resolve_llm_base_url(settings, base_url="https://example.com/")
        == "https://example.com/"
    )


def test_resolve_llm_base_url_uses_settings_when_explicit_is_none() -> None:
    settings = {"llm_base_url": "https://llm-proxy.eval.all-hands.dev/"}
    assert resolve_llm_base_url(settings) == "https://llm-proxy.eval.all-hands.dev/"


def test_resolve_llm_base_url_falls_back_to_default() -> None:
    assert resolve_llm_base_url({}) == DEFAULT_LLM_BASE_URL


def test_resolve_llm_base_url_treats_whitespace_as_empty() -> None:
    settings = {"llm_base_url": "   "}
    assert resolve_llm_base_url(settings) == DEFAULT_LLM_BASE_URL
