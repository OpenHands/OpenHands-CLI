"""Advanced tests for ACP implementation."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from acp import CancelNotification, LoadSessionRequest

from openhands.tools.file_editor.definition import FileEditorAction
from openhands_cli.acp_impl.agent import OpenHandsACPAgent
from openhands_cli.acp_impl.event import extract_action_locations


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def acp_agent(mock_connection):
    """Create an OpenHands ACP agent instance."""
    return OpenHandsACPAgent(mock_connection)


@pytest.mark.asyncio
async def test_get_or_create_conversation_caching(acp_agent, tmp_path):
    """Test that _get_or_create_conversation caches conversations."""
    session_id = str(uuid4())

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
    ):
        mock_agent = MagicMock()
        mock_load.return_value = mock_agent

        mock_conversation = MagicMock()
        mock_conv.return_value = mock_conversation

        # First call should create a new conversation
        conv1 = acp_agent._get_or_create_conversation(
            session_id=session_id, working_dir=str(tmp_path)
        )

        assert conv1 == mock_conversation
        assert session_id in acp_agent._active_sessions

        # Second call should return cached conversation
        conv2 = acp_agent._get_or_create_conversation(session_id=session_id)

        assert conv2 == conv1
        assert conv2 == mock_conversation
        # Conversation should only be created once
        mock_conv.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_pauses_conversation(acp_agent):
    """Test that cancelling a session pauses the conversation."""
    session_id = str(uuid4())
    notification = CancelNotification(sessionId=session_id)

    # Create a mock conversation and add it to active sessions
    mock_conversation = MagicMock()
    acp_agent._active_sessions[session_id] = mock_conversation

    await acp_agent.cancel(notification)

    # Verify pause was called
    mock_conversation.pause.assert_called_once()


@pytest.mark.asyncio
async def test_load_session_with_no_history(acp_agent, mock_connection):
    """Test loading a session with no history."""
    session_id = str(uuid4())
    request = LoadSessionRequest(sessionId=session_id, cwd="/test/path", mcpServers=[])

    # Create mock conversation with empty history
    mock_conversation = MagicMock()
    mock_conversation.state.events = []

    with patch.object(acp_agent, "_get_or_create_conversation") as mock_get:
        mock_get.return_value = mock_conversation

        await acp_agent.loadSession(request)

        # Verify no sessionUpdate was called
        mock_connection.sessionUpdate.assert_not_called()


def test_extract_action_locations_file_editor():
    """Test extracting locations from FileEditorAction."""
    # Test with path and view_range
    action = FileEditorAction(command="view", path="/test/file.py", view_range=[10, 20])

    locations = extract_action_locations(action)

    assert locations is not None
    assert len(locations) == 1
    assert locations[0].path == "/test/file.py"
    assert locations[0].line == 10


def test_extract_action_locations_file_editor_insert():
    """Test extracting locations from FileEditorAction with insert_line."""
    action = FileEditorAction(
        command="insert",
        path="/test/file.py",
        insert_line=5,
        new_str="print('hello')",
    )

    locations = extract_action_locations(action)

    assert locations is not None
    assert len(locations) == 1
    assert locations[0].path == "/test/file.py"
    assert locations[0].line == 5


def test_extract_action_locations_no_location():
    """Test extracting locations from action with no location info."""
    # Mock action that doesn't have location info
    mock_action = MagicMock()
    mock_action.path = None

    locations = extract_action_locations(mock_action)

    assert locations is None


def test_extract_action_locations_file_editor_no_range():
    """Test extracting locations from FileEditorAction without view_range."""
    action = FileEditorAction(command="view", path="/test/file.py")

    locations = extract_action_locations(action)

    assert locations is not None
    assert len(locations) == 1
    assert locations[0].path == "/test/file.py"
    # Line should not be set if no view_range or insert_line
    assert not hasattr(locations[0], "line") or locations[0].line is None
