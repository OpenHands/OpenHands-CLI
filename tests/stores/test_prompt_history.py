import json
from pathlib import Path

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
