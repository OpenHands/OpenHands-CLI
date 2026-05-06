import json
from pathlib import Path
from unittest.mock import patch

from openhands_cli.locations import get_project_id, get_prompt_history_path
from openhands_cli.stores.prompt_history import PromptHistoryStore


def test_project_id_is_stable():
    """Test that project ID remains the same for the same path."""
    id1 = get_project_id()
    id2 = get_project_id()
    assert id1 == id2
    assert len(id1) == 64


def test_prompt_history_store_append_load(mock_locations):
    """Test appending and loading prompt history."""
    # mock_locations handles environment variables and home dir mocking
    store = PromptHistoryStore()

    # Initially empty
    assert store.load() == []

    # Append some items
    store.append("first prompt")
    store.append("second prompt")
    store.append("second prompt")  # Duplicate, should be ignored
    store.append("third prompt")

    # Load items (should be newest first)
    history = store.load()
    assert history == ["third prompt", "second prompt", "first prompt"]


def test_prompt_history_max_entries(mock_locations):
    """Test that history is truncated to max_entries."""
    store = PromptHistoryStore(max_entries=3)

    store.append("p1")
    store.append("p2")
    store.append("p3")
    store.append("p4")

    history = store.load()
    assert len(history) == 3
    assert history == ["p4", "p3", "p2"]


def test_prompt_history_file_content(mock_locations):
    """Test that the history file contains expected JSON structure."""
    store = PromptHistoryStore()
    store.append("test prompt")

    path = Path(get_prompt_history_path())
    assert path.exists()

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["text"] == "test prompt"
    assert "timestamp" in data[0]


def test_prompt_history_corrupt_json(mock_locations):
    """Test handling of corrupt JSON in history file."""
    path = Path(get_prompt_history_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("invalid json", encoding="utf-8")

    store = PromptHistoryStore()
    entries = store.load_entries()
    assert entries == []


def test_prompt_history_invalid_format(mock_locations):
    """Test handling of unexpected JSON format (not a list)."""
    path = Path(get_prompt_history_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")

    store = PromptHistoryStore()
    entries = store.load_entries()
    assert entries == []


def test_prompt_history_read_error(mock_locations):
    """Test handling of OSError during reading."""
    path = Path(get_prompt_history_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()

    store = PromptHistoryStore()
    with patch("builtins.open", side_effect=OSError("Read failed")):
        entries = store.load_entries()
        assert entries == []


def test_prompt_history_permission_error(mock_locations):
    """Test handling of PermissionError during reading."""
    path = Path(get_prompt_history_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()

    store = PromptHistoryStore()
    with patch("builtins.open", side_effect=PermissionError("Permission denied")):
        entries = store.load_entries()
        assert entries == []


def test_prompt_history_write_error(mock_locations):
    """Test handling of OSError during writing."""
    store = PromptHistoryStore()

    # Mock open to fail only on write
    original_open = open

    def side_effect(file, mode="r", *args, **kwargs):
        if "w" in mode:
            raise OSError("Write failed")
        return original_open(file, mode, *args, **kwargs)

    with patch("builtins.open", side_effect=side_effect):
        # Should not raise exception
        store.append("new prompt")


def test_prompt_history_append_corrupt_load(mock_locations):
    """Test that append handles corrupt existing file by overwriting."""
    path = Path(get_prompt_history_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("invalid json", encoding="utf-8")

    store = PromptHistoryStore()
    store.append("new prompt")

    # Should have recovered and saved the new prompt
    assert store.load() == ["new prompt"]
