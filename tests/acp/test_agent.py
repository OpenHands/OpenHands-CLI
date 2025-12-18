"""Tests for the OpenHands ACP Agent."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from acp.schema import (
    AgentCapabilities,
    Implementation,
    NewSessionRequest,
    TextContentBlock,
)

from openhands_cli.acp_impl.agent import OpenHandsACPAgent


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def acp_agent(mock_connection):
    """Create an OpenHands ACP agent instance."""
    return OpenHandsACPAgent(mock_connection, "always-ask")


@pytest.mark.asyncio
async def test_initialize_with_configured_agent(acp_agent):
    """Test agent initialization when agent is configured."""
    # Mock load_agent_specs to succeed
    with patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load:
        mock_agent = MagicMock()
        mock_load.return_value = mock_agent

        response = await acp_agent.initialize(
            protocol_version=1,
            client_info=Implementation(name="test-client", version="1.0.0"),
        )

        assert response.protocol_version == 1
        assert isinstance(response.agent_capabilities, AgentCapabilities)
        assert response.agent_capabilities.load_session is True
        assert len(response.auth_methods) == 0  # No auth needed when configured


@pytest.mark.asyncio
async def test_initialize_without_configured_agent(acp_agent):
    """Test agent initialization when agent is not configured."""
    from openhands_cli.setup import MissingAgentSpec

    # Mock load_agent_specs to raise MissingAgentSpec
    with patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load:
        mock_load.side_effect = MissingAgentSpec("Not configured")

        response = await acp_agent.initialize(
            protocol_version=1,
            client_info=Implementation(name="test-client", version="1.0.0"),
        )

        assert response.protocol_version == 1
        assert len(response.auth_methods) == 0  # No auth methods for now


@pytest.mark.asyncio
async def test_authenticate(acp_agent):
    """Test authentication."""
    response = await acp_agent.authenticate(method_id="test-method")

    assert response is not None


@pytest.mark.asyncio
async def test_new_session_success(acp_agent, tmp_path):
    """Test creating a new session successfully."""
    # Mock the CLI utilities
    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
    ):
        # Mock agent
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        # Mock conversation
        mock_conversation = MagicMock()
        mock_conv.return_value = mock_conversation

        response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])

        # Verify session was created
        assert response.session_id is not None

        # Verify it's a valid UUID
        session_uuid = UUID(response.session_id)
        assert str(session_uuid) == response.session_id

        # Verify session is stored
        assert response.session_id in acp_agent._active_sessions
        assert acp_agent._active_sessions[response.session_id] == mock_conversation


@pytest.mark.asyncio
async def test_new_session_agent_not_configured(acp_agent, tmp_path):
    """Test creating a new session when agent is not configured."""
    from acp import RequestError

    from openhands_cli.setup import MissingAgentSpec

    # Mock load_agent_specs to raise MissingAgentSpec
    with patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load:
        mock_load.side_effect = MissingAgentSpec("Not configured")

        with pytest.raises(RequestError):
            await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])


@pytest.mark.asyncio
async def test_new_session_with_malformed_mcp_json(acp_agent, tmp_path, monkeypatch):
    """Test that malformed mcp.json raises a clear error in ACP."""
    from acp import RequestError

    from openhands_cli.mcp.mcp_utils import MCPConfigurationError

    request = NewSessionRequest(cwd=str(tmp_path), mcp_servers=[])

    # Mock load_agent_specs to raise MCPConfigurationError
    with patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load:
        mock_load.side_effect = MCPConfigurationError(
            "Invalid JSON: trailing characters at line 20 column 1"
        )

        # Should raise RequestError with helpful message
        with pytest.raises(RequestError) as exc_info:
            await acp_agent.new_session(
                cwd=request.cwd, mcp_servers=request.mcp_servers
            )

        # Verify the error contains helpful information
        error = exc_info.value
        assert error.code == -32602  # Invalid params error code
        assert error.data is not None
        assert "Invalid MCP configuration" in error.data.get("reason", "")
        assert "mcp.json" in error.data.get("help", "")


@pytest.mark.asyncio
async def test_new_session_with_malformed_mcp_json_integration(
    acp_agent, tmp_path, monkeypatch
):
    """Integration test verifying error handling with malformed mcp.json."""
    from acp import RequestError

    from openhands_cli.mcp.mcp_utils import MCPConfigurationError
    from openhands_cli.tui.settings.store import AgentStore

    request = NewSessionRequest(cwd=str(tmp_path), mcp_servers=[])

    # Mock AgentStore to inject our own load_mcp_configuration behavior
    original_init = AgentStore.__init__

    def mock_init(self):
        # Call original init
        original_init(self)

    def mock_load_mcp(self):
        # Simulate malformed mcp.json being detected
        raise MCPConfigurationError(
            "Invalid JSON: trailing characters at line 20 column 1"
        )

    with (
        patch.object(AgentStore, "__init__", mock_init),
        patch.object(AgentStore, "load_mcp_configuration", mock_load_mcp),
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load_specs,
    ):
        # Mock load_agent_specs to propagate the MCPConfigurationError
        mock_load_specs.side_effect = MCPConfigurationError(
            "Invalid JSON: trailing characters at line 20 column 1"
        )

        # RequestError raised when creating session with malformed mcp.json
        with pytest.raises(RequestError) as exc_info:
            await acp_agent.new_session(
                cwd=request.cwd, mcp_servers=request.mcp_servers
            )

        # Verify the error contains helpful information
        error = exc_info.value
        assert error.code == -32602  # Invalid params error code
        assert error.data is not None
        assert "Invalid MCP configuration" in error.data.get("reason", "")
        assert "mcp.json" in error.data.get("help", "")


@pytest.mark.asyncio
async def test_new_session_creates_working_directory(acp_agent, tmp_path):
    """Test that new session creates working directory if it doesn't exist."""
    # Create a path that doesn't exist yet
    new_dir = tmp_path / "subdir" / "workdir"

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
    ):
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        mock_conversation = MagicMock()
        mock_conv.return_value = mock_conversation

        await acp_agent.new_session(cwd=str(new_dir), mcp_servers=[])

        # Verify directory was created
        assert new_dir.exists()
        assert new_dir.is_dir()


@pytest.mark.asyncio
async def test_prompt_unknown_session(acp_agent):
    """Test prompt with unknown session ID.

    Should raise RequestError due to missing agent config.
    """
    from acp import RequestError

    content_blocks = [TextContentBlock(type="text", text="Hello")]

    # When session doesn't exist, _get_or_create_conversation will try to load it,
    # which requires agent configuration. This will fail with RequestError.
    with pytest.raises(RequestError):
        await acp_agent.prompt(session_id="unknown-session", prompt=content_blocks)


@pytest.mark.asyncio
async def test_prompt_empty_text(acp_agent):
    """Test prompt with empty text."""

    session_id = "test-session"

    # Create mock conversation
    mock_conversation = MagicMock()
    acp_agent._active_sessions[session_id] = mock_conversation

    # Test with empty prompt
    response = await acp_agent.prompt(
        session_id=session_id, prompt=[TextContentBlock(type="text", text="")]
    )

    assert response.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_prompt_success(acp_agent, mock_connection):
    """Test successful prompt processing."""
    from pathlib import Path

    from openhands.sdk import Message, TextContent
    from openhands.sdk.event.llm_convertible.message import MessageEvent

    # Create mock conversation with callbacks list
    # Store callbacks to trigger them after conversation.run
    mock_conversation = MagicMock()
    mock_conversation.state.events = []
    # Store the callbacks that will be set during newSession
    callbacks_holder = []

    # Create a real newSession to set up callbacks
    with patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load:
        # Mock agent specs
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = MagicMock(agent=mock_agent)

        with patch("openhands_cli.acp_impl.agent.Conversation") as MockConv:
            # Capture the callbacks parameter
            def capture_callbacks(*args, **kwargs):
                if "callbacks" in kwargs:
                    callbacks_holder.extend(kwargs["callbacks"])
                return mock_conversation

            MockConv.side_effect = capture_callbacks

            # Create session to set up callbacks
            response = await acp_agent.new_session(cwd=str(Path.cwd()), mcp_servers=[])
            session_id = response.session_id

    # Create a mock agent message event
    mock_message = Message(
        role="assistant", content=[TextContent(text="Hello, I can help!")]
    )
    mock_event = MessageEvent(source="agent", llm_message=mock_message)

    # Mock conversation.run to trigger callbacks
    async def mock_run(fn):
        # Call the real function which is conversation.run
        fn()
        mock_conversation.state.events.append(mock_event)
        # Trigger the callbacks that were set during newSession
        for callback in callbacks_holder:
            callback(mock_event)

    with patch("asyncio.to_thread", side_effect=mock_run):
        response = await acp_agent.prompt(
            session_id=session_id, prompt=[TextContentBlock(type="text", text="Hello")]
        )

        assert response.stop_reason == "end_turn"

        # Verify sessionUpdate was called (give it a moment for async tasks)
        import asyncio

        await asyncio.sleep(0.1)
        mock_connection.session_update.assert_called()


@pytest.mark.asyncio
async def test_cancel(acp_agent):
    """Test cancelling an operation."""
    session_id = "test-session"

    # Create mock conversation
    mock_conversation = MagicMock()
    acp_agent._active_sessions[session_id] = mock_conversation

    await acp_agent.cancel(session_id=session_id)

    # Verify pause was called
    mock_conversation.pause.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_unknown_session(acp_agent):
    """Test cancelling an unknown session.

    Should raise RequestError due to missing agent config.
    """
    from acp import RequestError

    # When session doesn't exist, cancel will try to create/load it,
    # which requires agent configuration. This will fail with RequestError.
    with pytest.raises(RequestError):
        await acp_agent.cancel(session_id="unknown-session")


@pytest.mark.asyncio
async def test_load_session_not_found(acp_agent):
    """Test loading a non-existent session.

    Should raise RequestError for invalid UUID.
    """
    from acp import RequestError

    # Invalid UUID format will raise RequestError
    with pytest.raises(RequestError):
        await acp_agent.load_session(
            session_id="non-existent", cwd="/test/path", mcp_servers=[]
        )


@pytest.mark.asyncio
async def test_load_session_success(acp_agent, mock_connection):
    """Test loading an existing session."""
    from uuid import uuid4

    from openhands.sdk import Message, TextContent
    from openhands.sdk.event.llm_convertible.message import MessageEvent

    session_id = str(uuid4())

    # Create mock conversation with history
    mock_conversation = MagicMock()
    user_message = Message(role="user", content=[TextContent(text="Hello")])
    agent_message = Message(role="assistant", content=[TextContent(text="Hi there!")])

    mock_conversation.state.events = [
        MessageEvent(source="user", llm_message=user_message),
        MessageEvent(source="agent", llm_message=agent_message),
    ]

    acp_agent._active_sessions[session_id] = mock_conversation

    await acp_agent.load_session(
        session_id=session_id, cwd="/test/path", mcp_servers=[]
    )

    # Verify sessionUpdate was called for:
    # 1. Agent message (user messages are skipped to avoid duplication in Zed UI)
    # 2. Available commands update
    assert mock_connection.session_update.call_count == 2


@pytest.mark.asyncio
async def test_set_session_mode(acp_agent):
    """Test setting session mode."""
    # Note: Since we removed _confirmation_mode dict, this test verifies that
    # set_session_mode can be called without error. The mode is now stored
    # directly in the conversation's confirmation policy, so we don't verify
    # it here (conversation doesn't exist yet in this test)
    response = await acp_agent.set_session_mode(
        session_id="test-session", mode_id="always-ask"
    )

    assert response is not None


@pytest.mark.asyncio
async def test_set_session_model(acp_agent):
    """Test setting session model."""
    response = await acp_agent.set_session_model(
        session_id="test-session", model_id="default"
    )

    assert response is not None


@pytest.mark.asyncio
async def test_ext_method(acp_agent):
    """Test extension method."""
    result = await acp_agent.ext_method("test-method", {"key": "value"})

    assert "error" in result


@pytest.mark.asyncio
async def test_ext_notification(acp_agent):
    """Test extension notification."""
    # Should not raise any errors
    await acp_agent.ext_notification("test-notification", {"key": "value"})


@pytest.mark.asyncio
async def test_prompt_with_image(acp_agent, mock_connection):
    """Test prompt with image content."""
    from pathlib import Path

    from acp.schema import ImageContentBlock

    from openhands.sdk import Message, TextContent
    from openhands.sdk.event.llm_convertible.message import MessageEvent

    # Create mock conversation with callbacks list
    mock_conversation = MagicMock()
    mock_conversation.state.events = []
    # Store the callbacks that will be set during newSession
    callbacks_holder = []

    # Create a real newSession to set up callbacks
    with patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load:
        # Mock agent specs
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = MagicMock(agent=mock_agent)

        with patch("openhands_cli.acp_impl.agent.Conversation") as MockConv:
            # Capture the callbacks parameter
            def capture_callbacks(*args, **kwargs):
                if "callbacks" in kwargs:
                    callbacks_holder.extend(kwargs["callbacks"])
                return mock_conversation

            MockConv.side_effect = capture_callbacks

            # Create session to set up callbacks
            response = await acp_agent.new_session(cwd=str(Path.cwd()), mcp_servers=[])
            session_id = response.session_id

    # Create a mock agent message event
    mock_message = Message(
        role="assistant", content=[TextContent(text="I see an OpenHands logo!")]
    )
    mock_event = MessageEvent(source="agent", llm_message=mock_message)

    # Mock conversation.run to trigger callbacks
    async def mock_run(fn):
        fn()
        mock_conversation.state.events.append(mock_event)
        # Trigger the callbacks that were set during newSession
        for callback in callbacks_holder:
            callback(mock_event)

    with patch("asyncio.to_thread", side_effect=mock_run):
        # Create request with both text and image
        # Note: ACP ImageContentBlock uses 'data' field which can be a URL
        # or base64 data
        response = await acp_agent.prompt(
            session_id=session_id,
            prompt=[
                TextContentBlock(type="text", text="What do you see in this image?"),
                ImageContentBlock(
                    type="image",
                    data="https://example.com/image.png",
                    mime_type="image/png",
                ),
            ],
        )

        assert response.stop_reason == "end_turn"

        # Verify sessionUpdate was called (give it a moment for async tasks)
        import asyncio

        await asyncio.sleep(0.1)
        mock_connection.session_update.assert_called()


@pytest.mark.asyncio
async def test_initialize_reports_image_capability(acp_agent):
    """Test that initialization reports image capability."""
    from acp.schema import Implementation

    with patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load:
        mock_agent = MagicMock()
        mock_load.return_value = mock_agent

        response = await acp_agent.initialize(
            protocol_version=1,
            client_info=Implementation(name="test-client", version="1.0.0"),
        )

        # Verify image capability is enabled
        assert response.agent_capabilities.prompt_capabilities.image is True


@pytest.mark.asyncio
async def test_new_session_with_mcp_servers(acp_agent, tmp_path):
    """Test creating a new session with MCP servers transforms env correctly."""
    from acp.schema import StdioMcpServer

    # Create MCP server with env as array (ACP format)
    mcp_server = StdioMcpServer(
        name="test-server",
        command="/usr/bin/node",
        args=["server.js"],
        env=[],  # Empty array - should be converted to {}
    )

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
    ):
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        mock_conversation = MagicMock()
        mock_conv.return_value = mock_conversation

        response = await acp_agent.new_session(
            cwd=str(tmp_path), mcp_servers=[mcp_server]
        )

        # Verify session was created
        assert response.session_id is not None

        # Verify load_agent_specs was called with transformed MCP servers dict
        mock_load.assert_called_once()
        call_kwargs = mock_load.call_args[1]
        assert "mcp_servers" in call_kwargs
        mcp_servers_dict = call_kwargs["mcp_servers"]

        # Verify it's a dict in Agent format (not ACP Pydantic models)
        assert isinstance(mcp_servers_dict, dict)
        assert "test-server" in mcp_servers_dict
        assert mcp_servers_dict["test-server"]["command"] == "/usr/bin/node"
        assert mcp_servers_dict["test-server"]["args"] == ["server.js"]
        assert mcp_servers_dict["test-server"]["env"] == {}  # Transformed from []
        assert "name" not in mcp_servers_dict["test-server"]  # Name used as key


@pytest.mark.asyncio
async def test_new_session_includes_modes(acp_agent, tmp_path):
    """Test that new_session returns modes in response."""
    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
    ):
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        mock_conversation = MagicMock()
        mock_conv.return_value = mock_conversation

        response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])

        # Verify modes are included
        assert response.modes is not None
        assert response.modes.current_mode_id == "always-ask"  # Default is always-ask
        assert len(response.modes.available_modes) == 3

        # Verify all modes are present
        mode_ids = {mode.id for mode in response.modes.available_modes}
        assert mode_ids == {"always-ask", "always-approve", "llm-approve"}


@pytest.mark.asyncio
async def test_load_session_includes_modes(acp_agent, tmp_path):
    """Test that load_session returns modes in response."""
    session_id = "12345678-1234-5678-1234-567812345678"

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
    ):
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        # Mock conversation with empty events (empty session)
        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        mock_conv.return_value = mock_conversation

        response = await acp_agent.load_session(
            session_id=session_id, cwd=str(tmp_path), mcp_servers=[]
        )

        # Verify modes are included
        assert response.modes is not None
        assert response.modes.current_mode_id == "always-ask"  # Default
        assert len(response.modes.available_modes) == 3


@pytest.mark.asyncio
async def test_set_session_mode_success(acp_agent, tmp_path):
    """Test setting session mode successfully."""
    # First create a session
    from openhands.sdk.security.confirmation_policy import AlwaysConfirm, NeverConfirm

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
    ):
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        mock_conversation = MagicMock()
        mock_conversation.state.confirmation_policy = AlwaysConfirm()
        mock_conversation.state.events = []

        # Set up set_confirmation_policy to actually update the policy
        def set_policy_side_effect(new_policy):
            mock_conversation.state.confirmation_policy = new_policy

        mock_conversation.set_confirmation_policy = MagicMock(
            side_effect=set_policy_side_effect
        )
        mock_conversation.set_security_analyzer = MagicMock()
        mock_conv.return_value = mock_conversation

        # Create session and get its ID
        session_response = await acp_agent.new_session(
            cwd=str(tmp_path), mcp_servers=[]
        )
        session_id = session_response.session_id

        # Now set the mode - this should update the policy
        response = await acp_agent.set_session_mode(
            mode_id="always-approve", session_id=session_id
        )

        assert response is not None

        # Verify set_confirmation_policy was called with a NeverConfirm policy
        mock_conversation.set_confirmation_policy.assert_called()
        # Get the last call (called once for initial, once for mode change)
        calls = mock_conversation.set_confirmation_policy.call_args_list
        last_policy = calls[-1][0][0]
        assert isinstance(last_policy, NeverConfirm)

        # Verify session update was sent
        acp_agent._conn.session_update.assert_called()
        call_args = acp_agent._conn.session_update.call_args
        assert call_args[1]["session_id"] == session_id
        update = call_args[1]["update"]
        assert update.current_mode_id == "always-approve"


@pytest.mark.asyncio
async def test_set_session_mode_invalid(acp_agent):
    """Test setting session mode with invalid mode ID."""
    from acp import RequestError

    session_id = "12345678-1234-5678-1234-567812345678"

    with pytest.raises(RequestError):
        await acp_agent.set_session_mode(mode_id="invalid", session_id=session_id)


@pytest.mark.asyncio
async def test_set_session_mode_updates_existing_conversation(acp_agent, tmp_path):
    """Test that setting mode updates existing conversation's confirmation policy."""
    from openhands.sdk.security.confirmation_policy import AlwaysConfirm, NeverConfirm

    with (
        patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
    ):
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        mock_conversation = MagicMock()
        mock_conversation.state.confirmation_policy = AlwaysConfirm()
        mock_conversation.state.events = []

        # Set up set_confirmation_policy to actually update the policy
        def set_policy_side_effect(new_policy):
            mock_conversation.state.confirmation_policy = new_policy

        mock_conversation.set_confirmation_policy = MagicMock(
            side_effect=set_policy_side_effect
        )
        mock_conversation.set_security_analyzer = MagicMock()
        mock_conv.return_value = mock_conversation

        # Create session
        response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        session_id = response.session_id

        # Conversation should be cached
        assert session_id in acp_agent._active_sessions

        # Change mode to always-approve
        await acp_agent.set_session_mode(
            mode_id="always-approve", session_id=session_id
        )

        # Verify set_confirmation_policy was called with a NeverConfirm policy
        mock_conversation.set_confirmation_policy.assert_called()
        # Get the last call (called once for initial mode, once for mode change)
        calls = mock_conversation.set_confirmation_policy.call_args_list
        last_policy = calls[-1][0][0]
        assert isinstance(last_policy, NeverConfirm)
