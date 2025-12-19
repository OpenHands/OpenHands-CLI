"""Integration tests for JSON mode functionality."""

import json
import sys
import uuid
from unittest.mock import MagicMock, Mock, patch

import pytest

from openhands.sdk.event import MessageEvent
from openhands.sdk.llm import Message
from openhands_cli.refactor.core.conversation_runner import ConversationRunner
from openhands_cli.simple_main import main as simple_main
from openhands_cli.utils import json_callback


class TestJsonModeIntegration:
    """Integration tests for JSON mode with headless operation."""

    @patch("openhands_cli.refactor.textual_app.main")
    def test_end_to_end_json_mode_enabled(self, mock_textual_main):
        """Test end-to-end JSON mode activation from CLI to app."""
        # Mock textual_main to return a UUID
        mock_textual_main.return_value = uuid.uuid4()

        test_args = ["openhands", "--headless", "--json", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        mock_textual_main.assert_called_once()
        kwargs = mock_textual_main.call_args.kwargs

        # Verify all the expected parameters are passed correctly
        assert kwargs["headless"] is True
        assert kwargs["json_mode"] is True
        assert kwargs["queued_inputs"] == ["test task"]

    @patch("openhands_cli.refactor.textual_app.main")
    def test_json_without_headless_disables_json_mode(self, mock_textual_main):
        """Test that --json without --headless doesn't enable JSON mode."""
        # Mock textual_main to return a UUID
        mock_textual_main.return_value = uuid.uuid4()

        test_args = ["openhands", "--json", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        mock_textual_main.assert_called_once()
        kwargs = mock_textual_main.call_args.kwargs

        # JSON mode should be False when headless is not enabled
        assert kwargs["headless"] is False
        assert kwargs["json_mode"] is False

    @pytest.mark.parametrize(
        "args_list,expected_json_mode",
        [
            (["--headless", "--task", "test"], False),
            (["--headless", "--json", "--task", "test"], True),
            (["--json", "--headless", "--task", "test"], True),
        ],
    )
    @patch("openhands_cli.refactor.textual_app.main")
    def test_json_mode_parameter_combinations(
        self, mock_textual_main, args_list, expected_json_mode
    ):
        """Test various parameter combinations for JSON mode."""
        # Mock textual_main to return a UUID
        mock_textual_main.return_value = uuid.uuid4()

        test_args = ["openhands"] + args_list

        with patch.object(sys, "argv", test_args):
            simple_main()

        mock_textual_main.assert_called_once()
        kwargs = mock_textual_main.call_args.kwargs
        assert kwargs["json_mode"] is expected_json_mode


class TestConversationRunnerEventCallback:
    """Tests for event callback functionality in ConversationRunner."""

    def test_conversation_runner_accepts_event_callback(self):
        """Test that ConversationRunner accepts event_callback parameter."""
        mock_callback = Mock()

        # Just test that the ConversationRunner can be instantiated with event_callback
        runner = ConversationRunner(
            conversation_id=uuid.uuid4(),
            running_state_callback=Mock(),
            confirmation_callback=Mock(),
            notification_callback=Mock(),
            visualizer=Mock(),
            event_callback=mock_callback,
        )

        # Verify the runner was created successfully
        assert runner is not None

    def test_conversation_runner_without_event_callback(self):
        """Test that ConversationRunner works without event_callback."""
        runner = ConversationRunner(
            conversation_id=uuid.uuid4(),
            running_state_callback=Mock(),
            confirmation_callback=Mock(),
            notification_callback=Mock(),
            visualizer=Mock(),
            event_callback=None,
        )

        # Verify the runner was created successfully
        assert runner is not None


class TestSetupConversationEventCallback:
    """Tests for event callback integration in setup_conversation."""

    @patch("openhands_cli.setup.Conversation")
    @patch("openhands_cli.setup.load_agent_specs")
    def test_setup_conversation_passes_event_callback_to_conversation(
        self, mock_load_agent, mock_conversation_cls
    ):
        """Test that setup_conversation passes event_callback to Conversation."""
        from openhands_cli.setup import setup_conversation
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm

        mock_agent = Mock()
        mock_load_agent.return_value = mock_agent
        mock_conversation = Mock()
        mock_conversation_cls.return_value = mock_conversation

        mock_callback = Mock()

        setup_conversation(
            conversation_id=uuid.uuid4(),
            confirmation_policy=AlwaysConfirm(),
            visualizer=Mock(),
            event_callback=mock_callback,
        )

        mock_conversation_cls.assert_called_once()
        kwargs = mock_conversation_cls.call_args.kwargs
        assert "callbacks" in kwargs
        assert kwargs["callbacks"] == [mock_callback]

    @patch("openhands_cli.setup.Conversation")
    @patch("openhands_cli.setup.load_agent_specs")
    def test_setup_conversation_without_event_callback(
        self, mock_load_agent, mock_conversation_cls
    ):
        """Test that setup_conversation works without event_callback."""
        from openhands_cli.setup import setup_conversation
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm

        mock_agent = Mock()
        mock_load_agent.return_value = mock_agent
        mock_conversation = Mock()
        mock_conversation_cls.return_value = mock_conversation

        setup_conversation(
            conversation_id=uuid.uuid4(),
            confirmation_policy=AlwaysConfirm(),
            visualizer=Mock(),
            event_callback=None,
        )

        mock_conversation_cls.assert_called_once()
        kwargs = mock_conversation_cls.call_args.kwargs
        assert kwargs["callbacks"] is None


class TestJsonCallbackIntegration:
    """Integration tests for json_callback with real event flow."""

    def test_json_callback_integration_with_message_event(self):
        """Test json_callback integration with a realistic MessageEvent."""
        # Create a realistic MessageEvent
        event = MessageEvent(
            llm_message=Message(role="user", content="Hello, this is a test message"),
            source="user",
        )

        with patch("builtins.print") as mock_print:
            json_callback(event)

            # Verify the output structure
            assert mock_print.call_count == 2
            mock_print.assert_any_call("--JSON Event--")

            # Get and validate the JSON output
            json_output = mock_print.call_args_list[1][0][0]
            parsed_json = json.loads(json_output)

            # Verify essential fields are present
            assert "llm_message" in parsed_json
            assert "source" in parsed_json
            assert parsed_json["source"] == "user"
            
            # Check the message content structure (it's a list of content objects)
            llm_message = parsed_json["llm_message"]
            assert "content" in llm_message
            content = llm_message["content"]
            assert isinstance(content, list)
            assert len(content) > 0
            assert content[0]["text"] == "Hello, this is a test message"

    def test_json_callback_as_event_callback_parameter(self):
        """Test that json_callback can be used as an event_callback parameter."""
        # This test verifies the function signature compatibility
        from openhands_cli.utils import json_callback

        # Create a mock event
        mock_event = Mock()
        mock_event.model_dump.return_value = {"test": "data"}

        # Verify json_callback can be called with an event (signature compatibility)
        with patch("builtins.print"):
            try:
                json_callback(mock_event)
            except Exception as e:
                pytest.fail(f"json_callback should be compatible as event_callback: {e}")

        mock_event.model_dump.assert_called_once()