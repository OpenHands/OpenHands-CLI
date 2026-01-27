"""Shared fixtures for E2E snapshot tests.

These fixtures set up the mock LLM server and agent configuration
for deterministic e2e testing with trajectory replay.
"""

import shutil
import sys
import uuid as uuid_module
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from e2e_tests.mock_llm_server import MockLLMServer
from e2e_tests.trajectory import get_trajectories_dir, load_trajectory
from tests.conftest import create_test_agent_config


# Fixed work directory path - writable on most systems and deterministic for snapshots
WORK_DIR = Path("/tmp/openhands-e2e-test-workspace")

# Fixed conversation ID for deterministic snapshots
FIXED_CONVERSATION_ID = uuid_module.UUID("00000000-0000-0000-0000-000000000001")

# Fixed Python interpreter path for deterministic snapshots
FIXED_PYTHON_PATH = "/openhands/micromamba/envs/openhands/bin/python"


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
    """Set environment variables for test paths.

    Using environment variables ensures all modules that call the getter functions
    will get the test paths, regardless of when they're imported.
    """
    # Set environment variables - the getter functions will read these
    monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(tmp_path))
    monkeypatch.setenv("OPENHANDS_CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setenv("OPENHANDS_WORK_DIR", str(work_dir))

    # Mock sys.executable to return a fixed path for deterministic snapshots
    monkeypatch.setattr(sys, "executable", FIXED_PYTHON_PATH)

    # Patch the terminal metadata to use the fixed Python path
    # The terminal tool runs `command -v python` in the shell to get the path,
    # so we need to patch the from_ps1_match method to override the result
    try:
        from openhands.tools.terminal.metadata import CmdOutputMetadata

        original_from_ps1_match = CmdOutputMetadata.from_ps1_match

        @classmethod
        def patched_from_ps1_match(cls, match):
            result = original_from_ps1_match.__func__(cls, match)
            result.py_interpreter_path = FIXED_PYTHON_PATH
            return result

        monkeypatch.setattr(CmdOutputMetadata, "from_ps1_match", patched_from_ps1_match)
    except ImportError:
        pass  # If the module doesn't exist, skip patching


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
    Returns a dict including 'conversation_id' that should be passed to OpenHandsApp.
    """
    conversations_dir, work_dir = setup_test_directories(tmp_path)
    patch_location_modules(monkeypatch, tmp_path, conversations_dir, work_dir)

    trajectory = load_trajectory(get_trajectories_dir() / "simple_echo_hello_world")
    server = MockLLMServer(trajectory=trajectory)
    base_url = server.start()

    create_test_agent_config(
        tmp_path, model="openai/gpt-4o", base_url=base_url, expose_secrets=True
    )

    yield {
        "persistence_dir": tmp_path,
        "conversations_dir": conversations_dir,
        "mock_server_url": base_url,
        "work_dir": work_dir,
        "trajectory": trajectory,
        "conversation_id": FIXED_CONVERSATION_ID,
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

    Returns a dict including 'conversation_id' that should be passed to OpenHandsApp.
    """
    trajectory_name = getattr(request, "param", "simple_echo_hello_world")

    conversations_dir, work_dir = setup_test_directories(tmp_path)
    patch_location_modules(monkeypatch, tmp_path, conversations_dir, work_dir)

    trajectory = load_trajectory(get_trajectories_dir() / trajectory_name)
    server = MockLLMServer(trajectory=trajectory)
    base_url = server.start()

    create_test_agent_config(
        tmp_path, model="openai/gpt-4o", base_url=base_url, expose_secrets=True
    )

    yield {
        "persistence_dir": tmp_path,
        "conversations_dir": conversations_dir,
        "mock_server_url": base_url,
        "work_dir": work_dir,
        "trajectory": trajectory,
        "trajectory_name": trajectory_name,
        "conversation_id": FIXED_CONVERSATION_ID,
    }

    server.stop()
    cleanup_work_dir()
