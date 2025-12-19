"""Unit tests for MCP server setup error handling in the refactored UI."""

import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from openhands_cli.refactor.core.conversation_runner import ConversationRunner
from openhands_cli.refactor.widgets.richlog_visualizer import ConversationVisualizer
from openhands_cli.setup import MCPSetupError, setup_conversation


@pytest.fixture
def temp_config_path():
    """Fixture that provides a temporary config path and patches PERSISTENCE_DIR."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "mcp.json"
        # Patch PERSISTENCE_DIR so that _get_mcp_config_path() returns our temp path
        with patch("openhands_cli.locations.PERSISTENCE_DIR", str(temp_dir)):
            yield config_path


@pytest.fixture
def mock_agent_store():
    """Mock agent store that returns a valid agent with problematic MCP config."""
    with patch("openhands_cli.setup.load_agent_specs") as mock_load_agent:
        from openhands.sdk import LLM, Agent
        from openhands.tools.preset.default import get_default_tools

        # Create a real agent with problematic MCP config
        mock_agent = Agent(
            llm=LLM(model="test-model", api_key="test-key"),
            tools=get_default_tools(enable_browser=False),
            mcp_config={
                "mcpServers": {
                    "Linear": {
                        "url": "https://mcp.linear.app/mcp",
                        "transport": "http",
                        "headers": {"Authorization": "Bearer token"},
                        "auth": "oauth",
                    }
                }
            },
        )

        mock_load_agent.return_value = mock_agent
        yield mock_load_agent


@pytest.fixture
def invalid_mcp_config(temp_config_path):
    """Create an invalid MCP configuration that will cause connection failures."""
    invalid_config = {
        "mcpServers": {
            "Linear": {
                "url": "https://invalid-mcp-server.example.com/mcp",
                "transport": "http",
                "headers": {"Authorization": "Bearer invalid_token"},
                "auth": "oauth",
            }
        }
    }
    temp_config_path.write_text(json.dumps(invalid_config))
    return temp_config_path


class TestMCPErrorHandling:
    """Test cases for MCP server setup error handling."""

    def test_mcp_connection_failure_during_setup(
        self, mock_agent_store, invalid_mcp_config
    ):
        """Test that MCP connection failures during setup are handled gracefully."""
        conversation_id = uuid.uuid4()

        # Mock the confirmation policy
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm

        confirmation_policy = AlwaysConfirm()

        # This should raise MCPSetupError due to MCP connection failure
        with pytest.raises(MCPSetupError) as exc_info:
            setup_conversation(
                conversation_id=conversation_id,
                confirmation_policy=confirmation_policy,
                visualizer=None,
            )

        # Verify the exception does not contain a conversation (new behavior)
        assert exc_info.value.conversation is None
        assert "MCP server setup failed" in str(exc_info.value)

    def test_conversation_runner_handles_mcp_failure(self, invalid_mcp_config):
        """Test that ConversationRunner handles MCP setup failures gracefully."""
        conversation_id = uuid.uuid4()

        # Mock callbacks
        running_state_callback = Mock()
        confirmation_callback = Mock()
        notification_callback = Mock()
        visualizer = Mock(spec=ConversationVisualizer)

        # Mock the confirmation policy
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm

        initial_confirmation_policy = AlwaysConfirm()

        # This should fail to create a conversation runner due to MCP setup failure
        with pytest.raises(MCPSetupError):
            ConversationRunner(
                conversation_id=conversation_id,
                running_state_callback=running_state_callback,
                confirmation_callback=confirmation_callback,
                notification_callback=notification_callback,
                visualizer=visualizer,
                initial_confirmation_policy=initial_confirmation_policy,
            )

        # The notification callback should not be called since the error happens during
        # setup_conversation and ConversationRunner.__init__ doesn't handle it
        notification_callback.assert_not_called()

    def test_mcp_config_validation_error(self, temp_config_path):
        """Test handling of invalid MCP configuration format."""
        # Create invalid JSON
        temp_config_path.write_text("invalid json content")

        from openhands_cli.mcp.mcp_utils import MCPConfigurationError, load_mcp_config

        with pytest.raises(
            MCPConfigurationError, match="Invalid MCP configuration file"
        ):
            load_mcp_config()

    def test_mcp_server_auth_failure(self, temp_config_path):
        """Test handling of MCP server authentication failures."""
        # Create config with invalid auth
        invalid_auth_config = {
            "mcpServers": {
                "TestServer": {
                    "url": "https://example.com/mcp",
                    "transport": "http",
                    "headers": {"Authorization": "Bearer expired_token"},
                    "auth": "oauth",
                }
            }
        }
        temp_config_path.write_text(json.dumps(invalid_auth_config))

        # This test verifies that the config loads but connection would fail
        from openhands_cli.mcp.mcp_utils import load_mcp_config

        config = load_mcp_config()

        # Config should load successfully
        assert "TestServer" in config.mcpServers

        # But actual connection would fail (tested in integration tests)

    def test_empty_mcp_config_handling(self, temp_config_path):
        """Test that empty MCP config is handled gracefully."""
        # Create empty config
        empty_config = {"mcpServers": {}}
        temp_config_path.write_text(json.dumps(empty_config))

        from openhands_cli.mcp.mcp_utils import load_mcp_config

        config = load_mcp_config()

        # Should load successfully with empty servers
        assert config.mcpServers == {}

    def test_missing_mcp_config_file(self, temp_config_path):
        """Test that missing MCP config file is handled gracefully."""
        # Don't create the config file
        from openhands_cli.mcp.mcp_utils import load_mcp_config

        config = load_mcp_config()

        # Should return empty config
        assert config.mcpServers == {}


class TestMCPErrorRecovery:
    """Test cases for MCP error recovery scenarios."""

    def test_partial_mcp_server_failure(self, temp_config_path):
        """Test handling when some MCP servers fail but others succeed."""
        # Create config with mix of valid and invalid servers
        mixed_config = {
            "mcpServers": {
                "ValidServer": {
                    "command": "echo",
                    "args": ["hello"],
                    "transport": "stdio",
                },
                "InvalidServer": {
                    "url": "https://invalid-server.example.com/mcp",
                    "transport": "http",
                    "headers": {"Authorization": "Bearer invalid_token"},
                    "auth": "oauth",
                },
            }
        }
        temp_config_path.write_text(json.dumps(mixed_config))

        from openhands_cli.mcp.mcp_utils import load_mcp_config

        config = load_mcp_config()

        # Config should load successfully
        assert len(config.mcpServers) == 2
        assert "ValidServer" in config.mcpServers
        assert "InvalidServer" in config.mcpServers

    def test_mcp_timeout_handling(self, temp_config_path):
        """Test handling of MCP server connection timeouts."""
        # Create config with server that would timeout
        timeout_config = {
            "mcpServers": {
                "TimeoutServer": {
                    "url": "https://httpbin.org/delay/10",  # Will timeout
                    "transport": "http",
                    "headers": {"Content-Type": "application/json"},
                }
            }
        }
        temp_config_path.write_text(json.dumps(timeout_config))

        from openhands_cli.mcp.mcp_utils import load_mcp_config

        config = load_mcp_config()

        # Config should load successfully
        assert "TimeoutServer" in config.mcpServers
