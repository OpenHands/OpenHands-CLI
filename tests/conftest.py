from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM
from openhands_cli.utils import get_default_cli_agent


# Fixture: temp_config_path - Shared MCP config path for tests
@pytest.fixture
def temp_config_path(monkeypatch, tmp_path):
    """Fixture that provides a temporary config path using environment variables.

    Using environment variables ensures all modules that call get_persistence_dir()
    will get the test path, regardless of when they're imported.

    This fixture is shared across all MCP tests to avoid duplication.
    """
    config_path = tmp_path / "mcp.json"
    # Set environment variable - works regardless of import order
    monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(tmp_path))
    yield config_path


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


# Fixture: mock_locations - Standardized location mocking via environment variables
@pytest.fixture
def mock_locations(tmp_path_factory, monkeypatch):
    """Set up mock locations using environment variables.

    This is the recommended approach for mocking location functions as it works
    regardless of import order and avoids issues with cached function references.
    """
    temp_persistence_dir = tmp_path_factory.mktemp("openhands_test")
    conversations_dir = temp_persistence_dir / "conversations"
    conversations_dir.mkdir(exist_ok=True)

    monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(temp_persistence_dir))
    monkeypatch.setenv("OPENHANDS_CONVERSATIONS_DIR", str(conversations_dir))

    return {
        "persistence_dir": temp_persistence_dir,
        "conversations_dir": conversations_dir,
    }


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
# Set up agent configuration for tests that need it
@pytest.fixture(scope="function")
def setup_test_agent_config(tmp_path_factory, monkeypatch):
    """
    Set up a minimal agent configuration for tests that need it.

    This fixture:
    - Creates a temporary directory for agent settings
    - Creates a minimal agent_settings.json file
    - Sets environment variables for location functions

    Tests that need agent configuration should explicitly request this fixture.
    """
    # Create a temporary directory for this test session
    temp_persistence_dir = tmp_path_factory.mktemp("openhands_test")
    conversations_dir = temp_persistence_dir / "conversations"
    conversations_dir.mkdir(exist_ok=True)

    # Set environment variables - works regardless of import order
    monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(temp_persistence_dir))
    monkeypatch.setenv("OPENHANDS_CONVERSATIONS_DIR", str(conversations_dir))

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

    yield temp_persistence_dir
