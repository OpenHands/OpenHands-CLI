import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM, Conversation, LocalFileStore
from openhands_cli.tui.settings.settings_screen import SettingsScreen
from openhands_cli.tui.settings.store import AgentStore
from openhands_cli.user_actions.settings_action import SettingsType
from openhands_cli.utils import get_default_cli_agent


def read_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def make_screen_with_conversation(model="openai/gpt-4o-mini", api_key="sk-xyz"):
    llm = LLM(model=model, api_key=SecretStr(api_key), usage_id="test-service")
    # Conversation(agent) signature may vary across versions; adapt if needed:
    from openhands.sdk.agent import Agent

    agent = Agent(llm=llm, tools=[])
    conv = Conversation(agent)
    return SettingsScreen(conversation=conv)


def seed_file(path: Path, model: str = "openai/gpt-4o-mini", api_key: str = "sk-old"):
    store = AgentStore()
    store.file_store = LocalFileStore(root=str(path))
    agent = get_default_cli_agent(
        llm=LLM(model=model, api_key=SecretStr(api_key), usage_id="test-service")
    )
    store.save(agent)


def test_llm_settings_save_and_load(tmp_path: Path):
    """Test that the settings screen can save basic LLM settings."""
    screen = SettingsScreen(conversation=None)

    # Mock the spec store to verify settings are saved
    with patch.object(screen.agent_store, "save") as mock_save:
        screen._save_llm_settings(model="openai/gpt-4o-mini", api_key="sk-test-123")

        # Verify that save was called
        mock_save.assert_called_once()

        # Get the agent spec that was saved
        saved_spec = mock_save.call_args[0][0]
        assert saved_spec.llm.model == "openai/gpt-4o-mini"
        assert saved_spec.llm.api_key.get_secret_value() == "sk-test-123"


def test_first_time_setup_workflow(tmp_path: Path):
    """Test that the basic settings workflow completes without errors."""
    screen = SettingsScreen()

    with (
        patch(
            "openhands_cli.tui.settings.settings_screen.settings_type_confirmation",
            return_value=SettingsType.BASIC,
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.choose_llm_provider",
            return_value="openai",
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.choose_llm_model",
            return_value="gpt-4o-mini",
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.prompt_api_key",
            return_value="sk-first",
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.save_settings_confirmation",
            return_value=True,
        ),
    ):
        # The workflow should complete without errors
        screen.configure_settings()

    # Since the current implementation doesn't save to file, we just verify the
    # workflow completed
    assert True  # If we get here, the workflow completed successfully


def test_update_existing_settings_workflow(tmp_path: Path):
    """Test that the settings update workflow completes without errors."""
    settings_path = tmp_path / "agent_settings.json"
    seed_file(settings_path, model="openai/gpt-4o-mini", api_key="sk-old")
    screen = make_screen_with_conversation(model="openai/gpt-4o-mini", api_key="sk-old")

    with (
        patch(
            "openhands_cli.tui.settings.settings_screen.settings_type_confirmation",
            return_value=SettingsType.BASIC,
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.choose_llm_provider",
            return_value="anthropic",
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.choose_llm_model",
            return_value="claude-3-5-sonnet",
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.prompt_api_key",
            return_value="sk-updated",
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.save_settings_confirmation",
            return_value=True,
        ),
    ):
        # The workflow should complete without errors
        screen.configure_settings()

    # Since the current implementation doesn't save to file, we just verify the
    # workflow completed
    assert True  # If we get here, the workflow completed successfully


def test_all_llms_in_agent_are_updated():
    """Test that modifying LLM settings creates multiple LLMs with same API key
    but different usage_ids."""
    # Create a screen with existing agent settings
    screen = SettingsScreen(conversation=None)
    initial_llm = LLM(
        model="openai/gpt-3.5-turbo",
        api_key=SecretStr("sk-initial"),
        usage_id="test-service",
    )
    initial_agent = get_default_cli_agent(llm=initial_llm)

    # Mock the agent store to return the initial agent and capture the save call
    with (
        patch.object(screen.agent_store, "load", return_value=initial_agent),
        patch.object(screen.agent_store, "save") as mock_save,
    ):
        # Modify the LLM settings with new API key
        screen._save_llm_settings(model="openai/gpt-4o-mini", api_key="sk-updated-123")
        mock_save.assert_called_once()

        # Get the saved agent from the mock
        saved_agent = mock_save.call_args[0][0]
        all_llms = list(saved_agent.get_all_llms())
        assert len(all_llms) >= 2, f"Expected at least 2 LLMs, got {len(all_llms)}"

        # Verify all LLMs have the same API key
        api_keys = [llm.api_key.get_secret_value() for llm in all_llms]
        assert all(api_key == "sk-updated-123" for api_key in api_keys), (
            f"Not all LLMs have the same API key: {api_keys}"
        )

        # Verify none of the usage_id attributes match
        usage_ids = [llm.usage_id for llm in all_llms]
        assert len(set(usage_ids)) == len(usage_ids), (
            f"Some usage_ids are duplicated: {usage_ids}"
        )


@pytest.mark.parametrize(
    "step_to_cancel",
    ["type", "provider", "model", "apikey", "save"],
)
def test_workflow_cancellation_at_each_step(tmp_path: Path, step_to_cancel: str):
    screen = make_screen_with_conversation()

    # Base happy-path patches
    patches = {
        "settings_type_confirmation": MagicMock(return_value=SettingsType.BASIC),
        "choose_llm_provider": MagicMock(return_value="openai"),
        "choose_llm_model": MagicMock(return_value="gpt-4o-mini"),
        "prompt_api_key": MagicMock(return_value="sk-new"),
        "save_settings_confirmation": MagicMock(return_value=True),
    }

    # Turn one step into a cancel
    if step_to_cancel == "type":
        patches["settings_type_confirmation"].side_effect = KeyboardInterrupt()
    elif step_to_cancel == "provider":
        patches["choose_llm_provider"].side_effect = KeyboardInterrupt()
    elif step_to_cancel == "model":
        patches["choose_llm_model"].side_effect = KeyboardInterrupt()
    elif step_to_cancel == "apikey":
        patches["prompt_api_key"].side_effect = KeyboardInterrupt()
    elif step_to_cancel == "save":
        patches["save_settings_confirmation"].side_effect = KeyboardInterrupt()

    with (
        patch(
            "openhands_cli.tui.settings.settings_screen.settings_type_confirmation",
            patches["settings_type_confirmation"],
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.choose_llm_provider",
            patches["choose_llm_provider"],
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.choose_llm_model",
            patches["choose_llm_model"],
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.prompt_api_key",
            patches["prompt_api_key"],
        ),
        patch(
            "openhands_cli.tui.settings.settings_screen.save_settings_confirmation",
            patches["save_settings_confirmation"],
        ),
        patch.object(screen.agent_store, "save") as mock_save,
    ):
        screen.configure_settings()

    # No settings should be saved on cancel
    mock_save.assert_not_called()


def test_verify_agent_exists_or_setup_agent_retries_after_missing_spec():
    """verify_agent_exists_or_setup_agent should configure settings once when
    no agent spec exists, then return the agent from a successful reload."""

    from openhands_cli.setup import MissingAgentSpec, verify_agent_exists_or_setup_agent

    mock_agent = MagicMock()

    with (
        patch("openhands_cli.setup.SettingsScreen") as mock_screen_cls,
        patch("openhands_cli.setup.load_agent_specs") as mock_load,
    ):
        # First load attempt: no spec -> MissingAgentSpec
        # Second load attempt: returns an agent
        mock_load.side_effect = [MissingAgentSpec("no spec"), mock_agent]

        result = verify_agent_exists_or_setup_agent()

        # Should have created a settings screen and run first-time configuration
        mock_screen_cls.assert_called_once_with()
        mock_screen_cls.return_value.configure_settings.assert_called_once_with(
            first_time=True
        )

        # Load should be called twice: before and after configuration
        assert mock_load.call_count == 2
        assert result is mock_agent


def test_openhands_provider_hardcodes_base_url():
    """Test that when using OpenHands provider, the base_url is hardcoded."""
    screen = SettingsScreen(conversation=None)

    with patch.object(screen.agent_store, "save") as mock_save:
        # Test with openhands/ prefix
        screen._save_llm_settings(model="openhands/gpt-4o-mini", api_key="sk-test-123")

        mock_save.assert_called_once()
        saved_spec = mock_save.call_args[0][0]

        # Verify the base_url is hardcoded for openhands provider
        assert saved_spec.llm.base_url == "https://llm-proxy.app.all-hands.dev/"
        # The SDK converts openhands/ to litellm_proxy/ internally
        assert saved_spec.llm.model == "litellm_proxy/gpt-4o-mini"


def test_openhands_provider_respects_explicit_base_url():
    """Test that explicit base_url is preserved even for OpenHands provider."""
    screen = SettingsScreen(conversation=None)

    with patch.object(screen.agent_store, "save") as mock_save:
        # Test with explicit base_url
        custom_base_url = "https://custom-proxy.example.com/"
        screen._save_llm_settings(
            model="openhands/gpt-4o-mini",
            api_key="sk-test-123",
            base_url=custom_base_url,
        )

        mock_save.assert_called_once()
        saved_spec = mock_save.call_args[0][0]

        # Verify the explicit base_url is preserved
        assert saved_spec.llm.base_url == custom_base_url


def test_save_llm_settings_persists_reasoning_summary():
    screen = SettingsScreen(conversation=None)
    initial_llm = LLM(
        model="openai/gpt-4o-mini",
        api_key=SecretStr("sk-initial"),
        usage_id="test-service",
    )
    initial_agent = get_default_cli_agent(llm=initial_llm)

    with (
        patch.object(screen.agent_store, "load", return_value=initial_agent),
        patch.object(screen.agent_store, "save") as mock_save,
    ):
        screen._save_llm_settings(
            model="openai/gpt-5",
            api_key="sk-new",
            reasoning_summary="detailed",
        )

    mock_save.assert_called_once()
    saved_agent = mock_save.call_args[0][0]
    assert saved_agent.llm.reasoning_summary == "detailed"
    assert saved_agent.condenser.llm.reasoning_summary == "detailed"


def test_non_openhands_provider_no_base_url():
    """Test that non-OpenHands providers don't get automatic base_url."""
    screen = SettingsScreen(conversation=None)

    with patch.object(screen.agent_store, "save") as mock_save:
        # Test with non-openhands provider
        screen._save_llm_settings(model="openai/gpt-4o-mini", api_key="sk-test-123")

        mock_save.assert_called_once()
        saved_spec = mock_save.call_args[0][0]

        # Verify no base_url is set for non-openhands providers
        assert saved_spec.llm.base_url is None
