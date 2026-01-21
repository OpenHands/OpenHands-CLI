import json
from datetime import UTC, datetime

import pytest

from openhands_cli.conversations.store.local import LocalFileStore


class TestLocalFileStore:
    @pytest.fixture
    def store(self, tmp_path):
        return LocalFileStore(base_dir=str(tmp_path))

    def test_create_creates_directory_structure(self, store, tmp_path):
        """Test that create() makes the necessary directories."""
        conv_id = store.create()
        assert (tmp_path / conv_id).exists()
        assert (tmp_path / conv_id / "events").exists()

    def test_create_with_id(self, store, tmp_path):
        """Test creating with a specific ID."""
        specific_id = "custom-id"
        store.create(specific_id)
        assert (tmp_path / specific_id).exists()

    def test_list_conversations_empty(self, store):
        """Test listing when no conversations exist."""
        assert store.list_conversations() == []

    def test_list_conversations_parses_metadata(self, store, tmp_path):
        """Test that list_conversations correctly parses event files."""
        conv_id = "test-conv-id"
        events_dir = tmp_path / conv_id / "events"
        events_dir.mkdir(parents=True)

        timestamp = "2024-01-01T12:00:00Z"

        user_event = {
            "timestamp": timestamp,
            "source": "user",
            "llm_message": {
                "role": "user",
                # SDK expects content as a list of content blocks
                "content": [{"type": "text", "text": "Hello world"}],
            },
        }

        with open(events_dir / "event-001.json", "w") as f:
            json.dump(user_event, f)

        convs = store.list_conversations()
        assert len(convs) == 1
        assert convs[0].id == conv_id
        assert convs[0].title == "Hello world"
        assert convs[0].created_at == datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    def test_exists(self, store, tmp_path):
        conv_id = "exists-check"
        (tmp_path / conv_id).mkdir()
        assert store.exists(conv_id)
        assert not store.exists("non-existent")

    def test_get_metadata_returns_none_if_missing(self, store):
        assert store.get_metadata("missing") is None

    def test_get_metadata_returns_data(self, store, tmp_path):
        conv_id = "meta-check"
        events_dir = tmp_path / conv_id / "events"
        events_dir.mkdir(parents=True)

        user_event = {
            "timestamp": "2024-02-01T10:00:00Z",
            "source": "user",
            "llm_message": {
                "role": "user",
                "content": [{"type": "text", "text": "Test Title"}],
            },
        }
        with open(events_dir / "event-0.json", "w") as f:
            json.dump(user_event, f)

        meta = store.get_metadata(conv_id)
        assert meta is not None
        assert meta.id == conv_id
        assert meta.title == "Test Title"

    def test_load_events(self, store, tmp_path):
        """Test loading events from files."""
        conv_id = "events-test"
        events_dir = tmp_path / conv_id / "events"
        events_dir.mkdir(parents=True)

        user_event = {
            "id": "1",
            "timestamp": "2024-01-01T12:00:00Z",
            "source": "user",
            "kind": "MessageEvent",
            "llm_message": {
                "role": "user",
                "content": [{"type": "text", "text": "Test Event"}],
            },
        }
        with open(events_dir / "event-0.json", "w") as f:
            json.dump(user_event, f)

        events = list(store.load_events(conv_id))
        assert len(events) == 1
        assert events[0].source == "user"

    def test_load_events_skips_malformed(self, store, tmp_path):
        """Test that malformed event files are skipped."""
        conv_id = "malformed-test"
        events_dir = tmp_path / conv_id / "events"
        events_dir.mkdir(parents=True)

        # Good event
        user_event = {
            "id": "1",
            "timestamp": "2024-01-01T12:00:00Z",
            "source": "user",
            "kind": "MessageEvent",  # Discriminator
            "llm_message": {
                "role": "user",
                "content": [{"type": "text", "text": "Good"}],
            },
        }
        with open(events_dir / "event-0.json", "w") as f:
            json.dump(user_event, f)

        # Bad event (garbage)
        with open(events_dir / "event-1.json", "w") as f:
            f.write("{ invalid json")

        events = list(store.load_events(conv_id))
        assert len(events) == 1

    def test_get_event_count(self, store, tmp_path):
        conv_id = "count-test"
        events_dir = tmp_path / conv_id / "events"
        events_dir.mkdir(parents=True)

        # Create 3 files
        for i in range(3):
            (events_dir / f"event-{i}.json").touch()

        assert store.get_event_count(conv_id) == 3
        assert store.get_event_count("non-existent") == 0

    def test_load_events_limits(self, store, tmp_path):
        conv_id = "limit-test"
        events_dir = tmp_path / conv_id / "events"
        events_dir.mkdir(parents=True)

        # Create 5 events
        for i in range(5):
            event = {
                "id": str(i),
                "timestamp": f"2024-01-01T12:00:0{i}Z",
                "source": "user",
                "kind": "MessageEvent",
                "llm_message": {
                    "role": "user",
                    "content": [{"type": "text", "text": f"Msg {i}"}],
                },
            }
            with open(events_dir / f"event-{i}.json", "w") as f:
                json.dump(event, f)

        # Test normal limit (first 2)
        events = list(store.load_events(conv_id, limit=2))
        assert len(events) == 2
        assert events[0].id == "0"
        assert events[1].id == "1"

        # Test reverse limit (last 2)
        events = list(store.load_events(conv_id, limit=2, start_from_newest=True))
        assert len(events) == 2
        assert events[0].id == "3"
        assert events[1].id == "4"
