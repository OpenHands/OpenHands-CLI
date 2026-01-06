# tests/test_settings_utils.py

from __future__ import annotations

import pytest
from pydantic import SecretStr

import openhands_cli.tui.modals.settings.utils as settings_utils
from openhands.sdk import LLM, Agent, LLMSummarizingCondenser


class FakeAgentStore:
    """Minimal stand-in for AgentStore that just records saved agents."""

    def __init__(self) -> None:
        self.saved_agents: list[Agent] = []

    def save(self, agent: Agent) -> None:
        self.saved_agents.append(agent)


@pytest.fixture
def deps(monkeypatch) -> FakeAgentStore:
    """
    Patch out persistence and default-agent construction so tests are fast
    and deterministic, while still using real Agent/LLM classes.
    """
    fake_store = FakeAgentStore()

    # Use our fake store instead of the real AgentStore singleton
    monkeypatch.setattr(settings_utils, "agent_store", fake_store)

    # When utils wants a default CLI agent, build a minimal real Agent from the LLM
    def _mock_get_default_cli_agent(llm: LLM) -> Agent:
        return Agent(llm=llm)

    monkeypatch.setattr(
        settings_utils, "get_default_cli_agent", _mock_get_default_cli_agent
    )

    # Default: pretend litellm extra body is not needed
    monkeypatch.setattr(
        settings_utils,
        "should_set_litellm_extra_body",
        lambda model_name: False,
    )
    monkeypatch.setattr(
        settings_utils,
        "get_llm_metadata",
        lambda model_name, llm_type: {"model_name": model_name, "llm_type": llm_type},
    )

    return fake_store


#
# 1. Preserve existing API key when user does not provide one
#


@pytest.mark.parametrize("existing_key", ["sk-existing", SecretStr("sk-existing")])
def test_preserves_existing_api_key_when_not_provided(
    deps: FakeAgentStore,
    existing_key,
) -> None:
    """If settings already exist and api_key_input
    is empty, we keep the existing key."""

    # Normalize to string for comparison
    existing_key_str = (
        existing_key.get_secret_value()
        if isinstance(existing_key, SecretStr)
        else existing_key
    )

    # Existing agent with a real LLM that has the existing key
    existing_agent = Agent(
        llm=LLM(
            model="openai/gpt-4o",
            api_key=existing_key,  # can be str or SecretStr
        )
    )

    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="openai",
        model="gpt-4o",
        custom_model=None,
        base_url=None,
        api_key_input=None,  # user didn't type anything
        memory_condensation_enabled=True,
    )

    # First, resolve data fields; this should pull in existing_agent.llm.api_key
    data.resolve_data_fields(existing_agent)  # mutates data.api_key_input
    assert data.api_key_input == existing_key_str

    # Now run through save_settings with that existing agent
    result = settings_utils.save_settings(data, existing_agent)
    assert result.success is True
    assert deps.saved_agents, "Expected agent_store.save to have been called"

    saved_agent = deps.saved_agents[-1]
    saved_key = saved_agent.llm.api_key
    if isinstance(saved_key, SecretStr):
        saved_key = saved_key.get_secret_value()
    assert saved_key == existing_key_str


#
# 2. Mode-specific fields: advanced vs basic should wipe the other mode's fields
#


@pytest.mark.parametrize(
    "mode, "
    "provider, "
    "model, "
    "custom_model, "
    "base_url, "
    "expected_model, "
    "expected_base_url, "
    "fields_cleared",
    [
        (
            "basic",
            "openai",
            "gpt-4o",
            "should-be-cleared",
            "https://advanced.example",
            "openai/gpt-4o",  # provider/model combined
            None,  # advanced base_url cleared
            ("custom_model", "base_url"),
        ),
        (
            "advanced",
            "openai",
            "gpt-4o",
            "my/custom-model",
            "https://advanced.example",
            "my/custom-model",  # custom model used directly
            "https://advanced.example",
            ("provider", "model"),
        ),
    ],
)
def test_mode_specific_fields_cleared_and_not_saved(
    deps: FakeAgentStore,
    mode: str,
    provider: str | None,
    model: str | None,
    custom_model: str | None,
    base_url: str | None,
    expected_model: str,
    expected_base_url: str | None,
    fields_cleared: tuple[str, str],
) -> None:
    """If mode is basic/advanced, values from the other mode are wiped and not used."""

    assert mode == "basic" or mode == "advanced"
    data = settings_utils.SettingsFormData(
        mode=mode,
        provider=provider,
        model=model,
        custom_model=custom_model,
        base_url=base_url,
        api_key_input="sk-123",
        memory_condensation_enabled=True,
    )

    # Resolve against "new user" (no existing agent)
    data.resolve_data_fields(existing_agent=None)

    # Check that irrelevant fields are cleared
    for field in fields_cleared:
        assert getattr(data, field) is None

    # And that the full model name behaves as expected
    assert data.get_full_model_name() == expected_model

    # Run the full save and assert we built the LLM correctly
    result = settings_utils.save_settings(data, existing_agent=None)
    assert result.success is True
    saved_agent = deps.saved_agents[-1]
    assert saved_agent.llm.model == expected_model
    assert saved_agent.llm.base_url == expected_base_url


#
# 3. API key required when there's no existing agent
#


def test_missing_api_key_errors_when_no_existing_agent() -> None:
    """New users must provide an API key; otherwise we get a validation error."""
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="openai",
        model="gpt-4o",
        custom_model=None,
        base_url=None,
        api_key_input=None,
        memory_condensation_enabled=True,
    )

    with pytest.raises(Exception) as exc:
        data.resolve_data_fields(existing_agent=None)

    assert "API Key is required" in str(exc.value)


def test_save_settings_wraps_errors_into_result(deps: FakeAgentStore) -> None:
    """save_settings should surface resolver errors as success=False."""
    # Invalid: advanced mode with missing custom_model/base_url
    data = settings_utils.SettingsFormData(
        mode="advanced",
        provider=None,
        model=None,
        custom_model=None,
        base_url=None,
        api_key_input="sk-123",
        memory_condensation_enabled=True,
    )

    result = settings_utils.save_settings(data, existing_agent=None)
    assert result.success is False
    # The error message should mention missing custom model/base url
    assert "Custom model is required" in (result.error_message or "")


#
# 4. Memory condensation: enabling/disabling & updating condenser LLM
#


@pytest.mark.parametrize("enabled", [True, False])
def test_memory_condensation_toggle(deps: FakeAgentStore, enabled: bool) -> None:
    """Toggling memory_condensation_enabled should enable/disable the condenser."""
    # Start with a real agent that has no condenser
    existing_agent = Agent(
        llm=LLM(model="openai/gpt-4o", api_key="sk-123"),
        condenser=None,
    )

    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="openai",
        model="gpt-4o",
        custom_model=None,
        base_url=None,
        api_key_input="sk-123",
        memory_condensation_enabled=enabled,
    )

    result = settings_utils.save_settings(data, existing_agent=existing_agent)
    assert result.success is True
    saved_agent = deps.saved_agents[-1]

    if enabled:
        assert isinstance(saved_agent.condenser, LLMSummarizingCondenser)
        # condenser LLM should have usage_id="condenser"
        assert saved_agent.condenser.llm.usage_id == "condenser"
    else:
        assert saved_agent.condenser is None


def test_existing_condenser_llm_updated(deps: FakeAgentStore) -> None:
    """If an agent already has a condenser,
    its LLM should be updated to the new model."""
    old_main_llm = LLM(model="openai/gpt-3.5", api_key="sk-old")
    old_condenser_llm = LLM(
        model="old/model",
        api_key="sk-old",
        usage_id="condenser",
    )
    existing_condenser = LLMSummarizingCondenser(llm=old_condenser_llm)
    existing_agent = Agent(llm=old_main_llm, condenser=existing_condenser)

    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="openai",
        model="gpt-4o",
        custom_model=None,
        base_url=None,
        api_key_input="sk-new",
        memory_condensation_enabled=True,
    )

    result = settings_utils.save_settings(data, existing_agent=existing_agent)
    assert result.success is True
    saved_agent = deps.saved_agents[-1]

    # Main LLM updated
    assert saved_agent.llm.model == "openai/gpt-4o"
    assert isinstance(saved_agent.llm.api_key, SecretStr)
    assert saved_agent.llm.api_key.get_secret_value() == "sk-new"

    # Condenser LLM updated to same model, usage_id="condenser"
    assert isinstance(saved_agent.condenser, LLMSummarizingCondenser)
    assert saved_agent.condenser.llm.model == "openai/gpt-4o"
    assert saved_agent.condenser.llm.usage_id == "condenser"


#
# 5. Extra litellm metadata wiring
#


def test_litellm_metadata_is_added_when_required(
    monkeypatch, deps: FakeAgentStore
) -> None:
    """When should_set_litellm_extra_body is True, we attach litellm_extra_body."""
    monkeypatch.setattr(
        settings_utils,
        "should_set_litellm_extra_body",
        lambda model_name: True,
    )

    metadata = {"foo": "bar"}

    monkeypatch.setattr(
        settings_utils,
        "get_llm_metadata",
        lambda model_name, llm_type: metadata | {"llm_type": llm_type},
    )

    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="openai",
        model="gpt-4o",
        custom_model=None,
        base_url=None,
        api_key_input="sk-123",
        memory_condensation_enabled=True,
    )

    result = settings_utils.save_settings(data, existing_agent=None)
    assert result.success is True

    saved_agent = deps.saved_agents[-1]

    # Main LLM should get metadata via litellm_extra_body["metadata"]
    assert saved_agent.llm.litellm_extra_body is not None
    assert saved_agent.llm.litellm_extra_body["metadata"]["foo"] == "bar"

    # If condensation is enabled for a new agent, a condenser is created as well
    assert isinstance(saved_agent.condenser, LLMSummarizingCondenser)
    assert saved_agent.condenser.llm.litellm_extra_body is not None
    assert saved_agent.condenser.llm.litellm_extra_body["metadata"]["foo"] == "bar"
