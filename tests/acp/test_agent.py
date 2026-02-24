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

from openhands_cli.acp_impl.agent import LocalOpenHandsACPAgent


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def acp_agent(mock_connection):
    """Create an OpenHands ACP agent instance."""
    return LocalOpenHandsACPAgent(mock_connection, "always-ask")


@pytest.mark.asyncio
async def test_initialize_returns_auth_methods_when_not_authenticated(acp_agent):
    """Test agent initialization returns auth method when not authenticated."""
    with patch.object(acp_agent, "_is_authenticated", return_value=False):
        response = await acp_agent.initialize(
            protocol_version=1,
            client_info=Implementation(name="test-client", version="1.0.0"),
        )

        assert response.protocol_version == 1
        assert isinstance(response.agent_capabilities, AgentCapabilities)
        assert response.agent_capabilities.load_session is True
        # Auth method returned when not authenticated
        assert response.auth_methods is not None
        assert len(response.auth_methods) == 1
        assert response.auth_methods[0].id == "oauth"
        assert response.auth_methods[0].field_meta == {"type": "agent"}


@pytest.mark.asyncio
async def test_initialize_no_auth_methods_when_authenticated(acp_agent):
    """Test agent initialization returns empty auth_methods when authenticated."""
    with patch.object(acp_agent, "_is_authenticated", return_value=True):
        response = await acp_agent.initialize(
            protocol_version=1,
            client_info=Implementation(name="test-client", version="1.0.0"),
        )

        assert response.protocol_version == 1
        assert isinstance(response.agent_capabilities, AgentCapabilities)
        # No auth methods when already authenticated
        assert len(response.auth_methods) == 0


@pytest.mark.asyncio
async def test_authenticate(acp_agent):
    """Test authentication."""
    with patch(
        "openhands_cli.auth.login_command.login_command",
        new_callable=AsyncMock,
    ):
        response = await acp_agent.authenticate(method_id="oauth")

        assert response is not None


@pytest.mark.asyncio
async def test_new_session_success(acp_agent, tmp_path):
    """Test creating a new session successfully."""
    # Mock the CLI utilities
    with (
        patch("openhands_cli.acp_impl.agent.local_agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.local_agent.Conversation") as mock_conv,
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
async def test_new_session_raises_auth_required_when_not_authenticated(
    mock_connection, tmp_path
):
    """Test that new_session raises auth_required when user is not authenticated."""
    from acp import RequestError

    from openhands_cli.setup import MissingAgentSpec

    # Create agent and mock _is_authenticated to return False
    agent = LocalOpenHandsACPAgent(mock_connection, "always-ask")

    with patch(
        "openhands_cli.acp_impl.agent.local_agent.load_agent_specs"
    ) as mock_load:
        mock_load.side_effect = MissingAgentSpec("Not configured")

        with pytest.raises(RequestError) as exc_info:
            await agent.new_session(cwd=str(tmp_path), mcp_servers=[])

        assert "Authentication required" in str(exc_info.value.data)


@pytest.mark.asyncio
async def test_new_session_agent_not_configured(acp_agent, tmp_path):
    """Test creating a new session when agent is not configured."""
    from acp import RequestError

    from openhands_cli.setup import MissingAgentSpec

    # Mock load_agent_specs to raise MissingAgentSpec - this will make
    # _is_authenticated return False, which raises auth_required
    with patch(
        "openhands_cli.acp_impl.agent.local_agent.load_agent_specs"
    ) as mock_load:
        mock_load.side_effect = MissingAgentSpec("Not configured")

        with pytest.raises(RequestError):
            await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])


@pytest.mark.asyncio
async def test_new_session_with_malformed_mcp_json(acp_agent, tmp_path, monkeypatch):
    """Test that malformed mcp.json raises a clear error in ACP."""
    from acp import RequestError

    from openhands_cli.mcp.mcp_utils import MCPConfigurationError

    request = NewSessionRequest(cwd=str(tmp_path), mcp_servers=[])

    # Mock load_agent_specs:
    # - First call (from _is_authenticated): return success
    # - Second call (from _setup_conversation): raise MCPConfigurationError
    with patch(
        "openhands_cli.acp_impl.agent.local_agent.load_agent_specs"
    ) as mock_load:
        mock_agent = MagicMock()
        mock_load.side_effect = [
            mock_agent,  # First call succeeds (auth check)
            MCPConfigurationError(
                "Invalid JSON: trailing characters at line 20 column 1"
            ),  # Second call fails
        ]

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

    request = NewSessionRequest(cwd=str(tmp_path), mcp_servers=[])

    # Mock load_agent_specs:
    # - First call (from _is_authenticated): return success
    # - Second call (from _setup_conversation): raise MCPConfigurationError
    with patch(
        "openhands_cli.acp_impl.agent.local_agent.load_agent_specs"
    ) as mock_load_specs:
        mock_agent = MagicMock()
        mock_load_specs.side_effect = [
            mock_agent,  # First call succeeds (auth check)
            MCPConfigurationError(
                "Invalid JSON: trailing characters at line 20 column 1"
            ),  # Second call fails
        ]

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
        patch("openhands_cli.acp_impl.agent.local_agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.local_agent.Conversation") as mock_conv,
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
    with patch(
        "openhands_cli.acp_impl.agent.local_agent.load_agent_specs"
    ) as mock_load:
        # Mock agent specs
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = MagicMock(agent=mock_agent)

        with patch("openhands_cli.acp_impl.agent.local_agent.Conversation") as MockConv:
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
    with patch(
        "openhands_cli.acp_impl.agent.local_agent.load_agent_specs"
    ) as mock_load:
        # Mock agent specs
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = MagicMock(agent=mock_agent)

        with patch("openhands_cli.acp_impl.agent.local_agent.Conversation") as MockConv:
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

    with patch(
        "openhands_cli.acp_impl.agent.local_agent.load_agent_specs"
    ) as mock_load:
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
        patch("openhands_cli.acp_impl.agent.local_agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.local_agent.Conversation") as mock_conv,
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

        # Verify load_agent_specs was called twice:
        # - First call: _is_authenticated check (no args)
        # - Second call: _setup_conversation with mcp_servers
        assert mock_load.call_count == 2

        # Check the second call has the transformed MCP servers dict
        call_kwargs = mock_load.call_args_list[1][1]
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
        patch("openhands_cli.acp_impl.agent.local_agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.local_agent.Conversation") as mock_conv,
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
async def test_new_session_with_resume_conversation_id(mock_connection, tmp_path):
    """Test that new_session uses resume_conversation_id when provided."""
    resume_id = "12345678-1234-1234-1234-123456789abc"
    agent = LocalOpenHandsACPAgent(mock_connection, "always-ask", resume_id)

    with (
        patch("openhands_cli.acp_impl.agent.local_agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.local_agent.Conversation") as mock_conv,
    ):
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        mock_conversation = MagicMock()
        mock_conv.return_value = mock_conversation

        # First new_session should use the resume_conversation_id
        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])

        # Verify the session ID is the resume_conversation_id
        assert response.session_id == resume_id

        # Verify the resume_conversation_id is cleared after first use
        assert agent._resume_conversation_id is None


@pytest.mark.asyncio
async def test_new_session_resume_id_only_used_once(mock_connection, tmp_path):
    """Test that resume_conversation_id is only used for the first new_session call."""
    resume_id = "12345678-1234-1234-1234-123456789abc"
    agent = LocalOpenHandsACPAgent(mock_connection, "always-ask", resume_id)

    with (
        patch("openhands_cli.acp_impl.agent.local_agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.local_agent.Conversation") as mock_conv,
    ):
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        mock_conversation = MagicMock()
        mock_conv.return_value = mock_conversation

        # First new_session should use the resume_conversation_id
        response1 = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        assert response1.session_id == resume_id

        # Second new_session should generate a new UUID
        response2 = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        assert response2.session_id != resume_id

        # Verify it's a valid UUID
        UUID(response2.session_id)


@pytest.mark.asyncio
async def test_new_session_replays_historic_events_on_resume(mock_connection, tmp_path):
    """Test that new_session replays historic events when resuming a conversation."""
    resume_id = "12345678-1234-1234-1234-123456789abc"
    agent = LocalOpenHandsACPAgent(mock_connection, "always-ask", resume_id)

    with (
        patch("openhands_cli.acp_impl.agent.local_agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.local_agent.Conversation") as mock_conv,
        patch(
            "openhands_cli.acp_impl.agent.base_agent.EventSubscriber"
        ) as mock_subscriber_class,
    ):
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        # Create mock events
        from openhands.sdk import Message, TextContent
        from openhands.sdk.event.llm_convertible.message import MessageEvent

        mock_event1 = MessageEvent(
            source="user",
            llm_message=Message(role="user", content=[TextContent(text="Hello")]),
        )
        mock_event2 = MessageEvent(
            source="agent",
            llm_message=Message(
                role="assistant", content=[TextContent(text="Hi there!")]
            ),
        )

        # Mock conversation with historic events
        mock_conversation = MagicMock()
        mock_conversation.state.events = [mock_event1, mock_event2]
        mock_conv.return_value = mock_conversation

        # Mock EventSubscriber
        mock_subscriber = AsyncMock()
        mock_subscriber_class.return_value = mock_subscriber

        # Call new_session with resume
        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])

        # Verify the session ID is the resume_conversation_id
        assert response.session_id == resume_id

        # Verify EventSubscriber was created for replaying events
        mock_subscriber_class.assert_called_with(resume_id, mock_connection)

        # Verify all historic events were replayed
        assert mock_subscriber.call_count == 2
        mock_subscriber.assert_any_call(mock_event1)
        mock_subscriber.assert_any_call(mock_event2)


@pytest.mark.asyncio
async def test_new_session_no_replay_for_new_conversation(mock_connection, tmp_path):
    """Test that new_session does NOT replay events for new conversations."""
    # No resume_conversation_id provided
    agent = LocalOpenHandsACPAgent(mock_connection, "always-ask")

    with (
        patch("openhands_cli.acp_impl.agent.local_agent.load_agent_specs") as mock_load,
        patch("openhands_cli.acp_impl.agent.local_agent.Conversation") as mock_conv,
        patch(
            "openhands_cli.acp_impl.agent.base_agent.EventSubscriber"
        ) as mock_subscriber_class,
    ):
        mock_agent = MagicMock()
        mock_agent.llm.model = "test-model"
        mock_load.return_value = mock_agent

        # Mock conversation with no events (new conversation)
        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        mock_conv.return_value = mock_conversation

        # Mock EventSubscriber
        mock_subscriber = AsyncMock()
        mock_subscriber_class.return_value = mock_subscriber

        # Call new_session without resume
        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])

        # Verify a new UUID was generated (not the resume ID)
        UUID(response.session_id)  # Should be a valid UUID

        # Verify EventSubscriber was NOT called for replaying events
        # (it may be created for _send_available_commands, but not called with events)
        mock_subscriber.assert_not_called()


class TestHasAwsCredentials:
    """Tests for _has_aws_credentials method."""

    def test_has_aws_credentials_with_access_key_env(self, acp_agent, monkeypatch):
        """Test detection of AWS_ACCESS_KEY_ID environment variable."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
        assert acp_agent._has_aws_credentials() is True

    def test_has_aws_credentials_with_secret_key_env(self, acp_agent, monkeypatch):
        """Test detection of AWS_SECRET_ACCESS_KEY environment variable."""
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
        assert acp_agent._has_aws_credentials() is True

    def test_has_aws_credentials_with_profile_env(self, acp_agent, monkeypatch):
        """Test detection of AWS_PROFILE environment variable."""
        monkeypatch.setenv("AWS_PROFILE", "my-profile")
        assert acp_agent._has_aws_credentials() is True

    def test_has_aws_credentials_with_default_profile_env(self, acp_agent, monkeypatch):
        """Test detection of AWS_DEFAULT_PROFILE environment variable."""
        monkeypatch.setenv("AWS_DEFAULT_PROFILE", "default")
        assert acp_agent._has_aws_credentials() is True

    def test_has_aws_credentials_with_credentials_file(self, acp_agent, tmp_path):
        """Test detection of ~/.aws/credentials file."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            aws_dir = tmp_path / ".aws"
            aws_dir.mkdir()
            (aws_dir / "credentials").touch()
            assert acp_agent._has_aws_credentials() is True

    def test_has_aws_credentials_with_config_file(self, acp_agent, tmp_path):
        """Test detection of ~/.aws/config file."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            aws_dir = tmp_path / ".aws"
            aws_dir.mkdir()
            (aws_dir / "config").touch()
            assert acp_agent._has_aws_credentials() is True

    def test_has_aws_credentials_returns_false_when_no_credentials(
        self, acp_agent, tmp_path, monkeypatch
    ):
        """Test returns False when no AWS credentials are available."""
        # Clear any AWS env vars
        for var in [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_PROFILE",
            "AWS_DEFAULT_PROFILE",
        ]:
            monkeypatch.delenv(var, raising=False)

        # Point home to a temp dir with no .aws folder
        with patch("pathlib.Path.home", return_value=tmp_path):
            assert acp_agent._has_aws_credentials() is False


class TestIsAuthenticatedWithAwsCredentials:
    """Tests for _is_authenticated method with AWS credentials fallback."""

    @pytest.mark.asyncio
    async def test_is_authenticated_returns_true_with_agent_specs(self, acp_agent):
        """Test _is_authenticated returns True when agent_settings.json exists."""
        with patch(
            "openhands_cli.acp_impl.agent.local_agent.load_agent_specs"
        ) as mock_load:
            mock_load.return_value = MagicMock()
            result = await acp_agent._is_authenticated()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_authenticated_falls_back_to_aws_credentials(
        self, acp_agent, monkeypatch
    ):
        """Test _is_authenticated checks AWS credentials when no agent_settings.json."""
        from openhands_cli.setup import MissingAgentSpec

        monkeypatch.setenv("AWS_PROFILE", "bedrock-user")

        with patch(
            "openhands_cli.acp_impl.agent.local_agent.load_agent_specs",
            side_effect=MissingAgentSpec("No settings"),
        ):
            result = await acp_agent._is_authenticated()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_authenticated_returns_false_when_no_credentials(
        self, acp_agent, tmp_path, monkeypatch
    ):
        """Test _is_authenticated returns False when no credentials exist."""
        from openhands_cli.setup import MissingAgentSpec

        # Clear AWS env vars
        for var in [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_PROFILE",
            "AWS_DEFAULT_PROFILE",
        ]:
            monkeypatch.delenv(var, raising=False)

        with (
            patch(
                "openhands_cli.acp_impl.agent.local_agent.load_agent_specs",
                side_effect=MissingAgentSpec("No settings"),
            ),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = await acp_agent._is_authenticated()
            assert result is False
