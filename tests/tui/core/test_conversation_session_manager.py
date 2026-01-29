"""Tests for ConversationSessionManager."""

import uuid
from unittest.mock import Mock

from openhands_cli.tui.core.conversation_session_manager import (
    ConversationSession,
    ConversationSessionManager,
)


class TestConversationSession:
    """Tests for ConversationSession dataclass."""

    def test_default_values(self):
        """Session should have None for runner and pane by default."""
        conv_id = uuid.uuid4()
        session = ConversationSession(conversation_id=conv_id)

        assert session.conversation_id == conv_id
        assert session.runner is None
        assert session.pane is None

    def test_with_runner_and_pane(self):
        """Session can hold runner and pane references."""
        conv_id = uuid.uuid4()
        runner = Mock()
        pane = Mock()
        session = ConversationSession(conversation_id=conv_id, runner=runner, pane=pane)

        assert session.runner is runner
        assert session.pane is pane


class TestConversationSessionManager:
    """Tests for ConversationSessionManager."""

    def test_init_sets_active_conversation(self):
        """Manager should store initial conversation ID as active."""
        initial_id = uuid.uuid4()
        manager = ConversationSessionManager(initial_id)

        assert manager.active_conversation_id == initial_id

    def test_active_session_returns_none_initially(self):
        """Active session should be None before any session is created."""
        manager = ConversationSessionManager(uuid.uuid4())

        assert manager.active_session is None

    def test_get_or_create_session_creates_new(self):
        """get_or_create_session should create a new session if not exists."""
        manager = ConversationSessionManager(uuid.uuid4())
        conv_id = uuid.uuid4()

        session = manager.get_or_create_session(conv_id)

        assert session is not None
        assert session.conversation_id == conv_id
        assert session.runner is None
        assert session.pane is None

    def test_get_or_create_session_returns_existing(self):
        """get_or_create_session should return existing session."""
        manager = ConversationSessionManager(uuid.uuid4())
        conv_id = uuid.uuid4()

        session1 = manager.get_or_create_session(conv_id)
        session2 = manager.get_or_create_session(conv_id)

        assert session1 is session2

    def test_get_session_returns_none_for_unknown(self):
        """get_session should return None for unknown conversation."""
        manager = ConversationSessionManager(uuid.uuid4())

        session = manager.get_session(uuid.uuid4())

        assert session is None

    def test_set_active_conversation_switches_id(self):
        """set_active_conversation should update active conversation ID."""
        initial_id = uuid.uuid4()
        new_id = uuid.uuid4()
        manager = ConversationSessionManager(initial_id)

        manager.set_active_conversation(new_id)

        assert manager.active_conversation_id == new_id

    def test_set_active_conversation_creates_session(self):
        """set_active_conversation should create session if not exists."""
        manager = ConversationSessionManager(uuid.uuid4())
        new_id = uuid.uuid4()

        manager.set_active_conversation(new_id)

        assert manager.get_session(new_id) is not None

    def test_set_runner_stores_runner(self):
        """set_runner should store runner for conversation."""
        manager = ConversationSessionManager(uuid.uuid4())
        conv_id = uuid.uuid4()
        runner = Mock()

        manager.set_runner(conv_id, runner)

        assert manager.get_runner(conv_id) is runner

    def test_set_runner_creates_session_if_needed(self):
        """set_runner should create session if it doesn't exist."""
        manager = ConversationSessionManager(uuid.uuid4())
        conv_id = uuid.uuid4()
        runner = Mock()

        manager.set_runner(conv_id, runner)

        session = manager.get_session(conv_id)
        assert session is not None
        assert session.runner is runner

    def test_set_pane_stores_pane(self):
        """set_pane should store pane for conversation."""
        manager = ConversationSessionManager(uuid.uuid4())
        conv_id = uuid.uuid4()
        pane = Mock()

        manager.set_pane(conv_id, pane)

        assert manager.get_pane(conv_id) is pane

    def test_get_pane_returns_none_for_unknown(self):
        """get_pane should return None for unknown conversation."""
        manager = ConversationSessionManager(uuid.uuid4())

        assert manager.get_pane(uuid.uuid4()) is None

    def test_get_runner_returns_none_for_unknown(self):
        """get_runner should return None for unknown conversation."""
        manager = ConversationSessionManager(uuid.uuid4())

        assert manager.get_runner(uuid.uuid4()) is None

    def test_has_cached_pane_true_when_pane_set(self):
        """has_cached_pane should return True when pane is set."""
        manager = ConversationSessionManager(uuid.uuid4())
        conv_id = uuid.uuid4()
        manager.set_pane(conv_id, Mock())

        assert manager.has_cached_pane(conv_id) is True

    def test_has_cached_pane_false_when_no_pane(self):
        """has_cached_pane should return False when no pane."""
        manager = ConversationSessionManager(uuid.uuid4())
        conv_id = uuid.uuid4()
        manager.get_or_create_session(conv_id)  # Create session without pane

        assert manager.has_cached_pane(conv_id) is False

    def test_has_cached_pane_false_for_unknown(self):
        """has_cached_pane should return False for unknown conversation."""
        manager = ConversationSessionManager(uuid.uuid4())

        assert manager.has_cached_pane(uuid.uuid4()) is False

    def test_has_cached_session_true_when_both_set(self):
        """has_cached_session should return True when both pane and runner set."""
        manager = ConversationSessionManager(uuid.uuid4())
        conv_id = uuid.uuid4()
        manager.set_pane(conv_id, Mock())
        manager.set_runner(conv_id, Mock())

        assert manager.has_cached_session(conv_id) is True

    def test_has_cached_session_false_when_only_pane(self):
        """has_cached_session should return False when only pane set."""
        manager = ConversationSessionManager(uuid.uuid4())
        conv_id = uuid.uuid4()
        manager.set_pane(conv_id, Mock())

        assert manager.has_cached_session(conv_id) is False

    def test_has_cached_session_false_when_only_runner(self):
        """has_cached_session should return False when only runner set."""
        manager = ConversationSessionManager(uuid.uuid4())
        conv_id = uuid.uuid4()
        manager.set_runner(conv_id, Mock())

        assert manager.has_cached_session(conv_id) is False

    def test_has_cached_session_false_for_unknown(self):
        """has_cached_session should return False for unknown conversation."""
        manager = ConversationSessionManager(uuid.uuid4())

        assert manager.has_cached_session(uuid.uuid4()) is False

    def test_active_session_returns_session_after_set_active(self):
        """active_session should return session after set_active_conversation."""
        manager = ConversationSessionManager(uuid.uuid4())
        new_id = uuid.uuid4()

        manager.set_active_conversation(new_id)

        assert manager.active_session is not None
        assert manager.active_session.conversation_id == new_id

    def test_multiple_sessions_isolated(self):
        """Multiple conversations should have isolated sessions."""
        manager = ConversationSessionManager(uuid.uuid4())
        id1 = uuid.uuid4()
        id2 = uuid.uuid4()
        runner1 = Mock(name="runner1")
        runner2 = Mock(name="runner2")
        pane1 = Mock(name="pane1")
        pane2 = Mock(name="pane2")

        manager.set_runner(id1, runner1)
        manager.set_pane(id1, pane1)
        manager.set_runner(id2, runner2)
        manager.set_pane(id2, pane2)

        assert manager.get_runner(id1) is runner1
        assert manager.get_pane(id1) is pane1
        assert manager.get_runner(id2) is runner2
        assert manager.get_pane(id2) is pane2
