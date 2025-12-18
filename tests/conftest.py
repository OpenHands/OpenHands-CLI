from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM
from openhands_cli.utils import get_default_cli_agent


# Fixture: mock_verified_models - Simplified model data
@pytest.fixture
def mock_verified_models():
    with (
        patch(
            "openhands_cli.user_actions.settings_action.VERIFIED_MODELS",
            {
                "openai": ["gpt-4o", "gpt-4o-mini"],
                "anthropic": ["claude-3-5-sonnet", "claude-3-5-haiku"],
            },
        ),
        patch(
            "openhands_cli.user_actions.settings_action.UNVERIFIED_MODELS_EXCLUDING_BEDROCK",
            {
                "openai": ["gpt-custom"],
                "anthropic": [],
                "custom": ["my-model"],
            },
        ),
    ):
        yield


# Fixture: mock_cli_interactions - Reusable CLI mock patterns
@pytest.fixture
def mock_cli_interactions():
    class Mocks:
        def __init__(self):
            self.p_confirm = patch(
                "openhands_cli.user_actions.settings_action.cli_confirm"
            )
            self.p_text = patch(
                "openhands_cli.user_actions.settings_action.cli_text_input"
            )
            self.cli_confirm = None
            self.cli_text_input = None

        def start(self):
            self.cli_confirm = self.p_confirm.start()
            self.cli_text_input = self.p_text.start()
            return self

        def stop(self):
            self.p_confirm.stop()
            self.p_text.stop()

    mocks = Mocks().start()
    try:
        yield mocks
    finally:
        mocks.stop()


# Fixture: setup_test_agent_config
# Automatically set up agent configuration for all tests
@pytest.fixture(autouse=True, scope="function")
def setup_test_agent_config(tmp_path_factory):
    """
    Automatically set up a minimal agent configuration for all tests.

    This fixture:
    - Creates a temporary directory for agent settings
    - Creates a minimal agent_settings.json file
    - Patches AgentStore to use the temporary directory
    - Runs for every test automatically (autouse=True)
    """
    # Create a temporary directory for this test session
    temp_persistence_dir = tmp_path_factory.mktemp("openhands_test")
    conversations_dir = temp_persistence_dir / "conversations"
    conversations_dir.mkdir(exist_ok=True)

    # Create minimal agent configuration
    # Use a mock LLM configuration that doesn't require real API keys
    llm = LLM(
        model="openai/gpt-4o-mini",
        api_key=SecretStr("sk-test-mock-key"),
        usage_id="test-agent",
    )

    # Get default agent configuration
    agent = get_default_cli_agent(llm=llm)

    # Save agent configuration to temporary directory
    agent_settings_path = temp_persistence_dir / "agent_settings.json"
    agent_settings_json = agent.model_dump_json()
    agent_settings_path.write_text(agent_settings_json)

    #  Also create the agent settings in the default location as a fallback
    # This ensures tests work even if the patch isn't applied early enough
    from openhands_cli import locations

    default_persistence_dir = Path(locations.PERSISTENCE_DIR)
    if not default_persistence_dir.exists():
        default_persistence_dir.mkdir(parents=True, exist_ok=True)
    default_agent_settings = default_persistence_dir / "agent_settings.json"
    if not default_agent_settings.exists():
        default_agent_settings.write_text(agent_settings_json)

    # Patch locations module
    with patch.multiple(
        "openhands_cli.locations",
        PERSISTENCE_DIR=str(temp_persistence_dir),
        CONVERSATIONS_DIR=str(conversations_dir),
    ):
        yield temp_persistence_dir
