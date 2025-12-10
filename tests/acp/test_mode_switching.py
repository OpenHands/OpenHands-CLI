"""Integration tests for confirmation mode switching in ACP agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acp.schema import TextContentBlock

from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    NeverConfirm,
)
from openhands_cli.acp_impl.agent import OpenHandsACPAgent
from openhands_cli.acp_impl.confirmation import get_available_modes
from openhands_cli.acp_impl.slash_commands import (
    get_confirmation_mode_from_conversation,
)


def create_mock_conversation_with_policy(initial_policy=None):
    """Create a mock conversation with a real confirmation policy that can be updated.

    Args:
        initial_policy: Initial confirmation policy (defaults to AlwaysConfirm)

    Returns:
        Mock conversation with working set_confirmation_policy
    """
    if initial_policy is None:
        initial_policy = AlwaysConfirm()

    mock_conversation = MagicMock()
    mock_conversation.state.events = []
    mock_conversation.state.confirmation_policy = initial_policy

    # Make set_confirmation_policy actually update the policy
    def set_policy_side_effect(new_policy):
        mock_conversation.state.confirmation_policy = new_policy

    mock_conversation.set_confirmation_policy = MagicMock(
        side_effect=set_policy_side_effect
    )
    mock_conversation.set_security_analyzer = MagicMock()

    return mock_conversation


class TestSessionModes:
    """Test session modes functionality."""

    def test_get_available_modes_structure(self):
        """Test that available modes have correct structure."""
        modes = get_available_modes()
        assert len(modes) == 3

        mode_ids = {mode.id for mode in modes}
        assert mode_ids == {"always-ask", "always-approve", "llm-approve"}

        # Check that all modes have required fields
        for mode in modes:
            assert mode.id
            assert mode.name
            assert mode.description

    def test_mode_descriptions_are_informative(self):
        """Test that mode descriptions are informative."""
        modes = get_available_modes()
        modes_by_id = {mode.id: mode for mode in modes}

        # Always-ask should mention permission
        assert modes_by_id["always-ask"].description
        assert "permission" in modes_by_id["always-ask"].description.lower()

        # Always-approve should mention automatic
        assert modes_by_id["always-approve"].description
        assert "automatically" in modes_by_id["always-approve"].description.lower()

        # LLM-approve should mention risk or high risk
        assert modes_by_id["llm-approve"].description
        llm_desc = modes_by_id["llm-approve"].description.lower()
        assert "llm" in llm_desc or "risk" in llm_desc


class TestAgentModeSwitching:
    """Test agent mode switching functionality."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock ACP connection."""
        return AsyncMock()

    @pytest.fixture
    def acp_agent(self, mock_connection):
        """Create an OpenHands ACP agent instance."""
        return OpenHandsACPAgent(mock_connection, "always-ask")

    @pytest.mark.asyncio
    async def test_agent_initializes_with_default_mode(self, mock_connection):
        """Test that agent initializes with specified mode."""
        agent = OpenHandsACPAgent(mock_connection, "always-approve")
        assert agent._initial_confirmation_mode == "always-approve"

    @pytest.mark.asyncio
    async def test_default_confirmation_mode_is_always_ask(self, mock_connection):
        """Test that the default confirmation mode for ACP is 'always-ask'."""
        # When no mode is specified, agent should default to "always-ask"
        agent = OpenHandsACPAgent(mock_connection, "always-ask")
        assert agent._initial_confirmation_mode == "always-ask"

        # Verify this matches the default parameter in run_acp_server
        import inspect

        from openhands_cli.acp_impl.agent import run_acp_server

        sig = inspect.signature(run_acp_server)
        default_mode = sig.parameters["initial_confirmation_mode"].default
        assert default_mode == "always-ask", (
            f"Expected default mode to be 'always-ask', got '{default_mode}'"
        )

    @pytest.mark.asyncio
    async def test_new_session_returns_mode_state(self, acp_agent, tmp_path):
        """Test that new_session returns session mode state."""
        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent
            mock_conv.return_value = MagicMock()

            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])

            # Verify modes are returned
            assert response.modes is not None
            assert response.modes.current_mode_id == "always-ask"
            assert len(response.modes.available_modes) == 3

    @pytest.mark.asyncio
    async def test_mode_not_persists_across_session(self, acp_agent, tmp_path):
        """Test that confirmation mode persists within a session."""
        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent

            mock_conversation = create_mock_conversation_with_policy()
            mock_conv.return_value = mock_conversation

            # Create session
            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

            # Initial mode should be default
            conversation = acp_agent._active_sessions[session_id]
            assert get_confirmation_mode_from_conversation(conversation) == "always-ask"

            # Send slash command to change mode
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/confirm always-approve")],
            )

            # Mode should be updated
            conversation = acp_agent._active_sessions[session_id]
            assert (
                get_confirmation_mode_from_conversation(conversation)
                == "always-approve"
            )

    @pytest.mark.asyncio
    async def test_slash_command_changes_conversation_policy(self, acp_agent, tmp_path):
        """Test that /confirm command updates the conversation's confirmation policy."""

        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent

            mock_conversation = create_mock_conversation_with_policy()
            mock_conv.return_value = mock_conversation

            # Create session
            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

            # Send slash command to change to always-approve
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/confirm always-approve")],
            )

            # Verify conversation policy was updated
            mock_conversation.set_confirmation_policy.assert_called()
            policy = mock_conversation.set_confirmation_policy.call_args[0][0]
            assert isinstance(policy, NeverConfirm)

    @pytest.mark.asyncio
    async def test_multiple_mode_switches_in_session(self, acp_agent, tmp_path):
        """Test switching modes multiple times within a session."""
        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent

            mock_conversation = create_mock_conversation_with_policy()
            mock_conv.return_value = mock_conversation

            # Create session
            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

            # Switch to always-approve
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/confirm always-approve")],
            )
            conversation = acp_agent._active_sessions[session_id]
            assert (
                get_confirmation_mode_from_conversation(conversation)
                == "always-approve"
            )

            # Switch to llm-approve
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/confirm llm-approve")],
            )
            conversation = acp_agent._active_sessions[session_id]
            assert (
                get_confirmation_mode_from_conversation(conversation) == "llm-approve"
            )

            # Switch back to always-ask
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/confirm always-ask")],
            )
            conversation = acp_agent._active_sessions[session_id]
            assert get_confirmation_mode_from_conversation(conversation) == "always-ask"

    @pytest.mark.asyncio
    async def test_invalid_mode_keeps_current_mode(self, acp_agent, tmp_path):
        """Test that invalid mode doesn't change current mode."""
        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent

            mock_conversation = create_mock_conversation_with_policy()
            mock_conv.return_value = mock_conversation

            # Create session
            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

            # Try to set invalid mode
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/confirm invalid-mode")],
            )

            # Mode should remain unchanged
            conversation = acp_agent._active_sessions[session_id]
            assert get_confirmation_mode_from_conversation(conversation) == "always-ask"

    @pytest.mark.asyncio
    async def test_different_sessions_have_independent_modes(self, acp_agent, tmp_path):
        """Test that different sessions can have different confirmation modes."""
        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent

            def create_mock_conversation(*args, **kwargs):
                mock_conversation = create_mock_conversation_with_policy()
                return mock_conversation

            mock_conv.side_effect = create_mock_conversation

            # Create first session
            response1 = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id1 = response1.session_id

            # Create second session
            response2 = await acp_agent.new_session(
                cwd=str(tmp_path / "session2"), mcp_servers=[]
            )
            session_id2 = response2.session_id

            # Change mode in first session
            await acp_agent.prompt(
                session_id=session_id1,
                prompt=[TextContentBlock(type="text", text="/confirm always-approve")],
            )

            # Change mode in second session to different value
            await acp_agent.prompt(
                session_id=session_id2,
                prompt=[TextContentBlock(type="text", text="/confirm llm-approve")],
            )

            # Verify modes are independent
            conversation1 = acp_agent._active_sessions[session_id1]
            conversation2 = acp_agent._active_sessions[session_id2]
            assert (
                get_confirmation_mode_from_conversation(conversation1)
                == "always-approve"
            )
            assert (
                get_confirmation_mode_from_conversation(conversation2) == "llm-approve"
            )


class TestSlashCommandIntegration:
    """Test slash command integration with agent."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock ACP connection."""
        return AsyncMock()

    @pytest.fixture
    def acp_agent(self, mock_connection):
        """Create an OpenHands ACP agent instance."""
        return OpenHandsACPAgent(mock_connection, "always-ask")

    @pytest.mark.asyncio
    async def test_help_command_returns_available_commands(self, acp_agent, tmp_path):
        """Test that /help command returns list of available commands."""
        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent

            mock_conversation = create_mock_conversation_with_policy()
            mock_conv.return_value = mock_conversation

            # Create session
            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

            # Send /help command
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/help")],
            )

            # Verify session_update was called with help text
            acp_agent._conn.session_update.assert_called()
            call_args = acp_agent._conn.session_update.call_args
            assert "session_id" in call_args[1]
            assert call_args[1]["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_unknown_slash_command_returns_error(self, acp_agent, tmp_path):
        """Test that unknown slash commands return helpful error."""
        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent

            mock_conversation = create_mock_conversation_with_policy()
            mock_conv.return_value = mock_conversation

            # Create session
            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

            # Send unknown command
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/unknown")],
            )

            # Verify error message was sent
            acp_agent._conn.session_update.assert_called()

    @pytest.mark.asyncio
    async def test_confirm_without_argument_shows_help(self, acp_agent, tmp_path):
        """Test that /confirm without argument shows help text."""
        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent

            mock_conversation = create_mock_conversation_with_policy()
            mock_conv.return_value = mock_conversation

            # Create session
            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

            # Get initial mode
            conversation = acp_agent._active_sessions[session_id]
            initial_mode = get_confirmation_mode_from_conversation(conversation)

            # Send /confirm without argument
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/confirm")],
            )

            # Mode should not change
            conversation = acp_agent._active_sessions[session_id]
            assert get_confirmation_mode_from_conversation(conversation) == initial_mode

            # Verify help text was sent
            acp_agent._conn.session_update.assert_called()

    @pytest.mark.asyncio
    async def test_slash_command_case_insensitive(self, acp_agent, tmp_path):
        """Test that slash commands are case-insensitive."""
        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent

            mock_conversation = create_mock_conversation_with_policy()
            mock_conv.return_value = mock_conversation

            # Create session
            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

            # Send uppercase /HELP command
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/HELP")],
            )

            # Should work without error
            acp_agent._conn.session_update.assert_called()

            # Send mixed case /CoNfIrM command
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="/CoNfIrM ALWAYS-APPROVE")],
            )

            # Mode should be updated
            conversation = acp_agent._active_sessions[session_id]
            assert (
                get_confirmation_mode_from_conversation(conversation)
                == "always-approve"
            )
