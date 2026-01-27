"""Shared fixtures for E2E snapshot tests.

These fixtures set up the mock LLM server and agent configuration
for deterministic e2e testing with trajectory replay.
"""

import pytest
from pydantic import SecretStr

from e2e_tests.mock_llm_server import MockLLMServer
from e2e_tests.trajectory import get_trajectories_dir, load_trajectory


@pytest.fixture
def mock_llm_setup(tmp_path, monkeypatch):
    """Fixture that sets up mock LLM server and agent config.

    This fixture:
    1. Patches locations module FIRST (before any imports that use it)
    2. Mocks UUID generation for deterministic conversation IDs
    3. Uses fixed paths for deterministic snapshots
    4. Starts the mock LLM server with trajectory replay
    5. Creates agent config pointing to the mock server
    6. Yields the config paths
    7. Cleans up the server on teardown
    """
    import shutil
    import uuid as uuid_module
    from pathlib import Path

    # Use a fixed UUID for deterministic snapshots
    fixed_uuid = uuid_module.UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(uuid_module, "uuid4", lambda: fixed_uuid)

    # Create directories with fixed names for deterministic paths in snapshots
    # We still use tmp_path as base but create predictable subdirectory names
    conversations_dir = tmp_path / "conversations"
    conversations_dir.mkdir(exist_ok=True)

    # Use a fixed path for work_dir that:
    # 1. Is writable on most systems (/tmp is typically writable)
    # 2. Is deterministic for snapshot comparison
    # We clean it up at the end of each test
    work_dir = Path("/tmp/openhands-e2e-test-workspace")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # CRITICAL: Patch the locations module DIRECTLY before any imports
    # This must happen before any module that imports from locations
    import openhands_cli.locations as locations_module

    monkeypatch.setattr(locations_module, "PERSISTENCE_DIR", str(tmp_path))
    monkeypatch.setattr(locations_module, "CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setattr(locations_module, "AGENT_SETTINGS_PATH", "agent_settings.json")
    # Use a fixed work directory path for deterministic snapshots
    # This path is writable on most systems (unlike /workspace)
    monkeypatch.setattr(locations_module, "WORK_DIR", str(work_dir))

    # Also patch the stores module which may have cached the values
    from openhands_cli.stores import agent_store as agent_store_module

    monkeypatch.setattr(agent_store_module, "PERSISTENCE_DIR", str(tmp_path))
    monkeypatch.setattr(agent_store_module, "CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setattr(
        agent_store_module, "AGENT_SETTINGS_PATH", "agent_settings.json"
    )
    monkeypatch.setattr(agent_store_module, "WORK_DIR", str(work_dir))

    # Load trajectory for deterministic replay
    trajectory = load_trajectory(get_trajectories_dir() / "simple_echo_hello_world")

    # Start mock server with trajectory
    server = MockLLMServer(trajectory=trajectory)
    base_url = server.start()

    # Import SDK modules AFTER patching
    from openhands.sdk import LLM
    from openhands_cli.utils import get_default_cli_agent

    # Create LLM pointing to mock server
    # Use "openai/gpt-4o" - SDK will use base_url via api_base param to litellm
    llm = LLM(
        model="openai/gpt-4o",
        api_key=SecretStr("sk-test-mock-key"),
        base_url=base_url,
        usage_id="test-agent",
    )

    # Create agent with the mock LLM
    agent = get_default_cli_agent(llm=llm)

    # Save agent config to temp location
    agent_settings_path = tmp_path / "agent_settings.json"
    config_json = agent.model_dump_json(context={"expose_secrets": True})
    agent_settings_path.write_text(config_json)

    yield {
        "persistence_dir": tmp_path,
        "conversations_dir": conversations_dir,
        "mock_server_url": base_url,
        "work_dir": work_dir,
        "trajectory": trajectory,
    }

    # Cleanup
    server.stop()
    # Clean up the fixed work directory
    if work_dir.exists():
        shutil.rmtree(work_dir)


@pytest.fixture
def mock_llm_with_trajectory(tmp_path, monkeypatch, request):
    """Fixture that sets up mock LLM server with a specified trajectory.

    Use this fixture when you need a specific trajectory for a test.
    Pass the trajectory name via pytest.mark.parametrize or indirect fixture.

    Usage:
        @pytest.mark.parametrize("mock_llm_with_trajectory",
                                 ["simple_echo_hello_world"], indirect=True)
        def test_something(self, mock_llm_with_trajectory):
            ...
    """
    import shutil
    import uuid as uuid_module
    from pathlib import Path

    trajectory_name = getattr(request, "param", "simple_echo_hello_world")

    # Use a fixed UUID for deterministic snapshots
    fixed_uuid = uuid_module.UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(uuid_module, "uuid4", lambda: fixed_uuid)

    # Create directories
    conversations_dir = tmp_path / "conversations"
    conversations_dir.mkdir(exist_ok=True)

    # Use a fixed path for work_dir that is writable and deterministic
    work_dir = Path("/tmp/openhands-e2e-test-workspace")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Patch locations module
    import openhands_cli.locations as locations_module

    monkeypatch.setattr(locations_module, "PERSISTENCE_DIR", str(tmp_path))
    monkeypatch.setattr(locations_module, "CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setattr(locations_module, "AGENT_SETTINGS_PATH", "agent_settings.json")
    monkeypatch.setattr(locations_module, "WORK_DIR", str(work_dir))

    from openhands_cli.stores import agent_store as agent_store_module

    monkeypatch.setattr(agent_store_module, "PERSISTENCE_DIR", str(tmp_path))
    monkeypatch.setattr(agent_store_module, "CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setattr(
        agent_store_module, "AGENT_SETTINGS_PATH", "agent_settings.json"
    )
    monkeypatch.setattr(agent_store_module, "WORK_DIR", str(work_dir))

    # Load specified trajectory
    trajectory = load_trajectory(get_trajectories_dir() / trajectory_name)

    # Start mock server
    server = MockLLMServer(trajectory=trajectory)
    base_url = server.start()

    # Create agent
    from openhands.sdk import LLM
    from openhands_cli.utils import get_default_cli_agent

    llm = LLM(
        model="openai/gpt-4o",
        api_key=SecretStr("sk-test-mock-key"),
        base_url=base_url,
        usage_id="test-agent",
    )
    agent = get_default_cli_agent(llm=llm)

    agent_settings_path = tmp_path / "agent_settings.json"
    config_json = agent.model_dump_json(context={"expose_secrets": True})
    agent_settings_path.write_text(config_json)

    yield {
        "persistence_dir": tmp_path,
        "conversations_dir": conversations_dir,
        "mock_server_url": base_url,
        "work_dir": work_dir,
        "trajectory": trajectory,
        "trajectory_name": trajectory_name,
    }

    # Cleanup
    server.stop()
    if work_dir.exists():
        shutil.rmtree(work_dir)
