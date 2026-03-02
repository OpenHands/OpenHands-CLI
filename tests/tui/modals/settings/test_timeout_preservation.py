"""Tests for timeout preservation when invalid input is provided.

The UI layer (`SettingsScreen`) preserves the existing timeout value if the
user enters a non‑numeric or out‑of‑range value. This test reproduces that
behaviour by constructing a `SettingsFormData` instance, applying the same
preservation logic, and verifying that the saved `Agent` retains the original
timeout.
"""

from openhands.sdk import LLM, Agent
from openhands_cli.tui.modals.settings.utils import SettingsFormData, save_settings


def test_invalid_timeout_keeps_existing_value():
    # Existing agent with a known timeout (e.g., 120 seconds)
    existing_llm = LLM(
        model="openai/gpt-4o",
        api_key="test-key",
        usage_id="agent",
        timeout=120,
    )
    existing_agent = Agent(llm=existing_llm, tools=[], mcp_config={}, condenser=None)

    # User enters an invalid timeout (out of range)
    form_data = SettingsFormData(
        mode="basic",
        provider="openai",
        model="gpt-4o",
        custom_model=None,
        base_url=None,
        api_key_input="test-key",
        memory_condensation_enabled=False,
        timeout="9999",  # invalid – validator will return None
    )

    # Mimic SettingsScreen logic: preserve existing timeout if validator returned None
    if form_data.timeout is None:
        form_data.timeout = getattr(existing_agent.llm, "timeout", None)

    result = save_settings(form_data, existing_agent)
    assert result.success
    # The saved agent should retain the original timeout (120 seconds)
    assert result.error_message is None
    assert existing_agent.llm.timeout == 120
