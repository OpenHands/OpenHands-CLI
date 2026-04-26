"""Root conftest.py - applies autouse fixtures to ALL tests including tui_e2e/."""

import os.path

import pytest


@pytest.fixture(autouse=True)
def isolate_test_persistence(tmp_path_factory, monkeypatch):
    """Ensure all tests use isolated temp directories instead of ~/.openhands/.

    This autouse fixture runs BEFORE every test and sets environment variables
    to redirect all OpenHands persistence to an isolated temp directory.
    This prevents tests from accidentally writing to the user's real
    ~/.openhands/ directory - including tests that don't use mock_locations.

    Mocks:
    - OPENHANDS_PERSISTENCE_DIR -> isolated temp dir
    - OPENHANDS_CONVERSATIONS_DIR -> isolated temp dir
    - PERSISTENCE_DIR -> isolated temp dir (legacy env var)
    - os.path.expanduser("~") -> isolated temp home (fallback when env not checked)
    """
    home_dir = tmp_path_factory.mktemp("test_home")
    persistence_dir = home_dir / ".openhands"
    persistence_dir.mkdir(exist_ok=True)
    conversations_dir = persistence_dir / "conversations"
    conversations_dir.mkdir(exist_ok=True)

    monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(persistence_dir))
    monkeypatch.setenv("OPENHANDS_CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setenv("PERSISTENCE_DIR", str(persistence_dir))

    original_expanduser = os.path.expanduser

    def mock_expanduser(path):
        path_str = str(path)
        if path_str == "~":
            return str(home_dir)
        elif path_str.startswith("~/"):
            return str(home_dir / path_str[2:])
        elif path_str.startswith("~"):
            return original_expanduser(path_str)
        return original_expanduser(path_str)

    monkeypatch.setattr(os.path, "expanduser", mock_expanduser)
