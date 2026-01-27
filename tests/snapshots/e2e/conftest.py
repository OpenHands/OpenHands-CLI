"""Shared fixtures for E2E snapshot tests.

These fixtures set up the mock LLM server and agent configuration
for deterministic e2e testing with trajectory replay.
"""

import shutil
import uuid as uuid_module
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from e2e_tests.mock_llm_server import MockLLMServer
from e2e_tests.trajectory import get_trajectories_dir, load_trajectory


# Fixed work directory path - writable on most systems and deterministic for snapshots
WORK_DIR = Path("/tmp/openhands-e2e-test-workspace")


def create_deterministic_uuid_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up deterministic sequential UUID generation.

    Creates UUIDs in format: 00000000-0000-0000-0000-000000000001, ...002, etc.
    This ensures reproducible snapshots while avoiding duplicate ID errors.
    """
    uuid_counter = [0]

    def deterministic_uuid4():
        uuid_counter[0] += 1
        return uuid_module.UUID(f"00000000-0000-0000-0000-{uuid_counter[0]:012d}")

    monkeypatch.setattr(uuid_module, "uuid4", deterministic_uuid4)


def setup_test_directories(tmp_path: Path) -> tuple[Path, Path]:
    """Create and return test directories.

    Returns:
        Tuple of (conversations_dir, work_dir)
    """
    conversations_dir = tmp_path / "conversations"
    conversations_dir.mkdir(exist_ok=True)

    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    return conversations_dir, WORK_DIR


def patch_location_modules(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    conversations_dir: Path,
    work_dir: Path,
) -> None:
    """Patch location modules with test paths.

    CRITICAL: This must happen before any module that imports from locations.
    """
    import openhands_cli.locations as locations_module
    from openhands_cli.stores import agent_store as agent_store_module

    # Patch locations module
    monkeypatch.setattr(locations_module, "PERSISTENCE_DIR", str(tmp_path))
    monkeypatch.setattr(locations_module, "CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setattr(locations_module, "AGENT_SETTINGS_PATH", "agent_settings.json")
    monkeypatch.setattr(locations_module, "WORK_DIR", str(work_dir))

    # Patch agent_store module (may have cached values)
    monkeypatch.setattr(agent_store_module, "PERSISTENCE_DIR", str(tmp_path))
    monkeypatch.setattr(agent_store_module, "CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setattr(
        agent_store_module, "AGENT_SETTINGS_PATH", "agent_settings.json"
    )
    monkeypatch.setattr(agent_store_module, "WORK_DIR", str(work_dir))


def create_mock_agent(base_url: str, tmp_path: Path) -> None:
    """Create and save agent config pointing to mock server."""
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


def cleanup_work_dir() -> None:
    """Clean up the fixed work directory."""
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)


@pytest.fixture
def mock_llm_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[dict[str, Any], None, None]:
    """Fixture that sets up mock LLM server with default trajectory.

    Uses 'simple_echo_hello_world' trajectory for deterministic replay.
    """
    create_deterministic_uuid_generator(monkeypatch)
    conversations_dir, work_dir = setup_test_directories(tmp_path)
    patch_location_modules(monkeypatch, tmp_path, conversations_dir, work_dir)

    trajectory = load_trajectory(get_trajectories_dir() / "simple_echo_hello_world")
    server = MockLLMServer(trajectory=trajectory)
    base_url = server.start()

    create_mock_agent(base_url, tmp_path)

    yield {
        "persistence_dir": tmp_path,
        "conversations_dir": conversations_dir,
        "mock_server_url": base_url,
        "work_dir": work_dir,
        "trajectory": trajectory,
    }

    server.stop()
    cleanup_work_dir()


@pytest.fixture
def mock_llm_with_trajectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Generator[dict[str, Any], None, None]:
    """Fixture that sets up mock LLM server with a specified trajectory.

    Usage:
        @pytest.mark.parametrize("mock_llm_with_trajectory",
                                 ["simple_echo_hello_world"], indirect=True)
        def test_something(self, mock_llm_with_trajectory):
            ...
    """
    trajectory_name = getattr(request, "param", "simple_echo_hello_world")

    create_deterministic_uuid_generator(monkeypatch)
    conversations_dir, work_dir = setup_test_directories(tmp_path)
    patch_location_modules(monkeypatch, tmp_path, conversations_dir, work_dir)

    trajectory = load_trajectory(get_trajectories_dir() / trajectory_name)
    server = MockLLMServer(trajectory=trajectory)
    base_url = server.start()

    create_mock_agent(base_url, tmp_path)

    yield {
        "persistence_dir": tmp_path,
        "conversations_dir": conversations_dir,
        "mock_server_url": base_url,
        "work_dir": work_dir,
        "trajectory": trajectory,
        "trajectory_name": trajectory_name,
    }

    server.stop()
    cleanup_work_dir()
