from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM
from openhands_cli.utils import get_default_cli_agent


@dataclass
class MockLocations:
    """Typed container for mock location paths used in tests."""

    persistence_dir: Path
    conversations_dir: Path
    work_dir: Path
    home_dir: Path


# =============================================================================
# Shared helper functions for agent configuration setup
# =============================================================================


def create_test_agent_config(
    persistence_dir: Path,
    *,
    model: str = "openai/gpt-4o-mini",
    api_key: str = "sk-test-mock-key",
    base_url: str | None = None,
    expose_secrets: bool = False,
) -> Path:
    """Create and save a test agent configuration.

    This is a shared helper function used by multiple test fixtures to avoid
    code duplication. It creates a minimal agent configuration and saves it
    to the specified persistence directory.

    Args:
        persistence_dir: Directory where agent_settings.json will be saved
        model: LLM model identifier (default: openai/gpt-4o-mini)
        api_key: Mock API key (default: sk-test-mock-key)
        base_url: Optional base URL for mock LLM server
        expose_secrets: Whether to expose secrets in JSON output (default: False)

    Returns:
        Path to the created agent_settings.json file
    """
    llm_kwargs = {
        "model": model,
        "api_key": SecretStr(api_key),
        "usage_id": "test-agent",
    }
    if base_url:
        llm_kwargs["base_url"] = base_url

    llm = LLM(**llm_kwargs)
    agent = get_default_cli_agent(llm=llm)

    agent_settings_path = persistence_dir / "agent_settings.json"
    if expose_secrets:
        config_json = agent.model_dump_json(context={"expose_secrets": True})
    else:
        config_json = agent.model_dump_json()
    agent_settings_path.write_text(config_json)

    return agent_settings_path


def setup_test_persistence_dir(base_path: Path) -> tuple[Path, Path]:
    """Create persistence and conversations directories for testing.

    Args:
        base_path: Base path where directories will be created

    Returns:
        Tuple of (persistence_dir, conversations_dir)
    """
    persistence_dir = base_path
    conversations_dir = persistence_dir / "conversations"
    conversations_dir.mkdir(exist_ok=True)
    return persistence_dir, conversations_dir


# =============================================================================
# Fixtures
# =============================================================================


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


# Fixture: mock_locations - Standardized location mocking via environment variables
@pytest.fixture
def mock_locations(tmp_path_factory, monkeypatch) -> MockLocations:
    """Set up mock locations using environment variables and mock expanduser.

    Mocks:
    - OPENHANDS_PERSISTENCE_DIR, OPENHANDS_CONVERSATIONS_DIR, OPENHANDS_WORK_DIR
    - os.path.expanduser("~") returns home_dir
    """
    import os.path

    home_dir = tmp_path_factory.mktemp("home")
    persistence_dir = home_dir / ".openhands"
    persistence_dir.mkdir(exist_ok=True)
    conversations_dir = persistence_dir / "conversations"
    conversations_dir.mkdir(exist_ok=True)
    work_dir = tmp_path_factory.mktemp("openhands_work")

    monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(persistence_dir))
    monkeypatch.setenv("OPENHANDS_CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setenv("OPENHANDS_WORK_DIR", str(work_dir))

    original_expanduser = os.path.expanduser

    def mock_expanduser(path):
        if path == "~":
            return str(home_dir)
        elif path.startswith("~/"):
            return str(home_dir / path[2:])
        elif path.startswith("~"):
            return original_expanduser(path)
        return path

    monkeypatch.setattr("os.path.expanduser", mock_expanduser)

    return MockLocations(
        persistence_dir=persistence_dir,
        conversations_dir=conversations_dir,
        work_dir=work_dir,
        home_dir=home_dir,
    )


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
    persistence_dir, conversations_dir = setup_test_persistence_dir(
        temp_persistence_dir
    )

    # Set environment variables - works regardless of import order
    monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(persistence_dir))
    monkeypatch.setenv("OPENHANDS_CONVERSATIONS_DIR", str(conversations_dir))

    # Create agent configuration using shared helper
    create_test_agent_config(persistence_dir)

    yield persistence_dir
