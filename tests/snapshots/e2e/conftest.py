"""Shared fixtures for E2E snapshot tests.

These fixtures set up the mock LLM server and agent configuration
for deterministic e2e testing with trajectory replay.
"""

import shutil
import sys
import uuid as uuid_module
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import create_test_agent_config
from tui_e2e.mock_llm_server import MockLLMServer
from tui_e2e.trajectory import get_trajectories_dir, load_trajectory


# Fixed work directory path - writable on most systems and deterministic for snapshots
WORK_DIR = Path("/tmp/openhands-e2e-test-workspace")

# Fixed conversation ID for deterministic snapshots
FIXED_CONVERSATION_ID = uuid_module.UUID("00000000-0000-0000-0000-000000000001")

# Fixed Python interpreter path for deterministic snapshots
FIXED_PYTHON_PATH = "/openhands/micromamba/envs/openhands/bin/python"

# Fixed OS description for deterministic snapshots
# (kernel version varies between environments)
FIXED_OS_DESCRIPTION = "Linux (kernel 6.0.0-test)"


@dataclass
class E2ETestEnvironment:
    """Container for e2e test environment paths."""

    persistence_dir: Path
    conversations_dir: Path
    work_dir: Path
    conversation_id: uuid_module.UUID


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


def patch_location_env_vars(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    conversations_dir: Path,
    work_dir: Path,
) -> None:
    """Set environment variables for test paths.

    Using environment variables ensures all modules that call the getter functions
    will get the test paths, regardless of when they're imported.
    """
    monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(tmp_path))
    monkeypatch.setenv("OPENHANDS_CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setenv("OPENHANDS_WORK_DIR", str(work_dir))


def patch_deterministic_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch paths for deterministic snapshot testing.

    This ensures that sys.executable and Python interpreter paths are fixed
    to produce consistent snapshots across different environments.
    """
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

    # Patch get_os_description to return a fixed value
    # The kernel version varies between environments (CI vs local, different runners)
    # which causes snapshot mismatches
    try:
        import openhands_cli.utils

        monkeypatch.setattr(
            openhands_cli.utils, "get_os_description", lambda: FIXED_OS_DESCRIPTION
        )
    except ImportError:
        pass  # If the module doesn't exist, skip patching


def cleanup_work_dir() -> None:
    """Clean up the fixed work directory."""
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)


# =============================================================================
# Base fixture - autouse for all e2e tests
# =============================================================================


@pytest.fixture(autouse=True)
def e2e_test_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[E2ETestEnvironment, None, None]:
    """Base fixture that sets up the test environment for all e2e tests.

    This fixture is autouse=True, so it runs automatically for every test
    in the tests/snapshots/e2e/ directory. It:
    - Creates test directories (conversations, work)
    - Sets environment variables for test paths
    - Patches paths for deterministic snapshots

    Note: This only affects tests in tests/snapshots/e2e/ since conftest.py
    is scoped to this directory.
    """
    conversations_dir, work_dir = setup_test_directories(tmp_path)
    patch_location_env_vars(monkeypatch, tmp_path, conversations_dir, work_dir)
    patch_deterministic_paths(monkeypatch)

    yield E2ETestEnvironment(
        persistence_dir=tmp_path,
        conversations_dir=conversations_dir,
        work_dir=work_dir,
        conversation_id=FIXED_CONVERSATION_ID,
    )

    cleanup_work_dir()


# =============================================================================
# Specialized fixtures that build on the base environment
# =============================================================================


@pytest.fixture
def mock_llm_setup(
    e2e_test_environment: E2ETestEnvironment,
) -> Generator[dict[str, Any], None, None]:
    """Fixture that sets up mock LLM server with default trajectory.

    Uses 'simple_echo_hello_world' trajectory for deterministic replay.
    Returns a dict including 'conversation_id' that should be passed to OpenHandsApp.
    """
    trajectory = load_trajectory(get_trajectories_dir() / "simple_echo_hello_world")
    server = MockLLMServer(trajectory=trajectory)
    base_url = server.start()

    create_test_agent_config(
        e2e_test_environment.persistence_dir,
        model="openai/gpt-4o",
        base_url=base_url,
        expose_secrets=True,
    )

    yield {
        "persistence_dir": e2e_test_environment.persistence_dir,
        "conversations_dir": e2e_test_environment.conversations_dir,
        "mock_server_url": base_url,
        "work_dir": e2e_test_environment.work_dir,
        "trajectory": trajectory,
        "conversation_id": e2e_test_environment.conversation_id,
    }

    server.stop()


@pytest.fixture
def mock_llm_with_trajectory(
    e2e_test_environment: E2ETestEnvironment, request: pytest.FixtureRequest
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

    trajectory = load_trajectory(get_trajectories_dir() / trajectory_name)
    server = MockLLMServer(trajectory=trajectory)
    base_url = server.start()

    create_test_agent_config(
        e2e_test_environment.persistence_dir,
        model="openai/gpt-4o",
        base_url=base_url,
        expose_secrets=True,
    )

    yield {
        "persistence_dir": e2e_test_environment.persistence_dir,
        "conversations_dir": e2e_test_environment.conversations_dir,
        "mock_server_url": base_url,
        "work_dir": e2e_test_environment.work_dir,
        "trajectory": trajectory,
        "trajectory_name": trajectory_name,
        "conversation_id": e2e_test_environment.conversation_id,
    }

    server.stop()


@pytest.fixture
def first_time_user_setup(
    e2e_test_environment: E2ETestEnvironment,
) -> dict[str, Any]:
    """Fixture for testing first-time user experience (no agent configured).

    Unlike mock_llm_setup, this does NOT create agent_settings.json,
    simulating a user who has never configured the CLI before.
    """
    # NOTE: We intentionally do NOT call create_test_agent_config() here
    # to simulate a first-time user with no agent configured

    return {
        "persistence_dir": e2e_test_environment.persistence_dir,
        "conversations_dir": e2e_test_environment.conversations_dir,
        "work_dir": e2e_test_environment.work_dir,
        "conversation_id": e2e_test_environment.conversation_id,
    }
