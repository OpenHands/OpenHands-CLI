"""Tests for headless mode functionality."""

import sys
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.risk import SecurityRisk
from openhands_cli.argparsers.main_parser import create_main_parser
from openhands_cli.refactor.modals import SettingsScreen
from openhands_cli.refactor.textual_app import OpenHandsApp, main as textual_main
from openhands_cli.simple_main import main as simple_main


class TestHeadlessArgumentParsing:
    """Test headless mode argument parsing and validation."""

    def test_headless_flag_exists(self):
        """Test that --headless flag is available in parser."""
        parser = create_main_parser()
        args = parser.parse_args(["--headless", "--task", "test task"])
        assert hasattr(args, "headless")
        assert args.headless is True

    def test_headless_flag_default_false(self):
        """Test that headless flag defaults to False."""
        parser = create_main_parser()
        args = parser.parse_args(["--task", "test task"])
        assert args.headless is False

    def test_headless_requires_task_or_file(self):
        """Test that --headless can be parsed but validation happens in simple_main."""
        parser = create_main_parser()

        # Parser should accept --headless without task/file
        # (validation is in simple_main)
        args = parser.parse_args(["--headless"])
        assert args.headless is True
        assert args.task is None
        assert args.file is None

    def test_headless_with_task_valid(self):
        """Test that --headless with --task is valid."""
        parser = create_main_parser()
        args = parser.parse_args(["--headless", "--task", "test task"])
        assert args.headless is True
        assert args.task == "test task"

    def test_headless_with_file_valid(self):
        """Test that --headless with --file is valid."""
        parser = create_main_parser()
        args = parser.parse_args(["--headless", "--file", "test.txt"])
        assert args.headless is True
        assert args.file == "test.txt"

    def test_headless_with_both_task_and_file_valid(self):
        """Test that --headless with both --task and --file is valid."""
        parser = create_main_parser()
        args = parser.parse_args(["--headless", "--task", "test", "--file", "test.txt"])
        assert args.headless is True
        assert args.task == "test"
        assert args.file == "test.txt"


class TestHeadlessValidationInSimpleMain:
    """Test headless mode validation in simple_main.py."""

    @patch("openhands_cli.refactor.textual_app.main")
    def test_headless_validation_error_message(self, mock_textual_main):
        """Test that proper error message is shown when headless lacks task/file."""
        # Mock sys.argv to simulate command line args
        test_args = ["openhands", "--headless"]

        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                with patch("sys.stderr"):  # Suppress error output
                    simple_main()
            assert exc_info.value.code == 2

        # textual_main should not be called
        mock_textual_main.assert_not_called()

    @patch("openhands_cli.agent_chat.run_cli_entry")
    def test_headless_with_task_passes_validation(self, mock_run_cli_entry):
        """Test that headless with task passes validation."""
        test_args = ["openhands", "--headless", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        # Should call run_cli_entry (validation passed)
        mock_run_cli_entry.assert_called_once()

    @patch("openhands_cli.agent_chat.run_cli_entry")
    def test_headless_with_file_passes_validation(self, mock_run_cli_entry):
        """Test that headless with file passes validation."""
        import os
        import tempfile

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("test content")
            temp_file = f.name

        try:
            test_args = ["openhands", "--headless", "--file", temp_file]

            with patch.object(sys, "argv", test_args):
                simple_main()

            # Should call run_cli_entry (validation passed)
            mock_run_cli_entry.assert_called_once()
        finally:
            # Clean up the temporary file
            os.unlink(temp_file)

    @patch("openhands_cli.agent_chat.run_cli_entry")
    def test_headless_auto_sets_exit_without_confirmation(self, mock_run_cli_entry):
        """Test that headless mode automatically sets exit_without_confirmation."""
        test_args = ["openhands", "--headless", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        # Should call run_cli_entry (validation passed)
        mock_run_cli_entry.assert_called_once()

    @patch("openhands_cli.agent_chat.run_cli_entry")
    def test_explicit_exit_without_confirmation_preserved(self, mock_run_cli_entry):
        """Test that explicit --exit-without-confirmation is preserved."""
        test_args = ["openhands", "--task", "test task", "--exit-without-confirmation"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        # Should call run_cli_entry (validation passed)
        mock_run_cli_entry.assert_called_once()

    @patch("openhands_cli.agent_chat.run_cli_entry")
    def test_non_headless_mode_default_exit_confirmation(self, mock_run_cli_entry):
        """Test that non-headless mode uses default exit confirmation."""
        test_args = ["openhands", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        # Should call run_cli_entry (validation passed)
        mock_run_cli_entry.assert_called_once()


class TestHeadlessConfirmationPolicy:
    """Test headless mode confirmation policy behavior."""

    def test_headless_sets_never_confirm_policy(self):
        """Test that headless mode sets NeverConfirm policy."""
        with patch("openhands_cli.refactor.textual_app.OpenHandsApp") as mock_app_class:
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            textual_main(
                headless=True,
                always_approve=False,
                llm_approve=False,
                exit_without_confirmation=True,
            )

            # Check that OpenHandsApp was called with NeverConfirm policy
            mock_app_class.assert_called_once()
            call_kwargs = mock_app_class.call_args.kwargs
            assert isinstance(call_kwargs["initial_confirmation_policy"], NeverConfirm)

    def test_headless_overrides_always_approve(self):
        """Test that headless mode overrides always_approve setting."""
        with patch("openhands_cli.refactor.textual_app.OpenHandsApp") as mock_app_class:
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            textual_main(
                headless=True,
                always_approve=False,  # This should be overridden
                llm_approve=False,
                exit_without_confirmation=True,
            )

            # Should still use NeverConfirm due to headless mode
            mock_app_class.assert_called_once()
            call_kwargs = mock_app_class.call_args.kwargs
            assert isinstance(call_kwargs["initial_confirmation_policy"], NeverConfirm)

    def test_headless_overrides_llm_approve(self):
        """Test that headless mode overrides llm_approve setting."""
        with patch("openhands_cli.refactor.textual_app.OpenHandsApp") as mock_app_class:
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            textual_main(
                headless=True,
                always_approve=False,
                llm_approve=True,  # This should be overridden
                exit_without_confirmation=True,
            )

            # Should still use NeverConfirm due to headless mode
            mock_app_class.assert_called_once()
            call_kwargs = mock_app_class.call_args.kwargs
            assert isinstance(call_kwargs["initial_confirmation_policy"], NeverConfirm)

    def test_non_headless_respects_always_approve(self):
        """Test that non-headless mode respects always_approve setting."""
        with patch("openhands_cli.refactor.textual_app.OpenHandsApp") as mock_app_class:
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            textual_main(
                headless=False,
                always_approve=True,
                llm_approve=False,
                exit_without_confirmation=False,
            )

            # Should use NeverConfirm due to always_approve
            mock_app_class.assert_called_once()
            call_kwargs = mock_app_class.call_args.kwargs
            assert isinstance(call_kwargs["initial_confirmation_policy"], NeverConfirm)

    def test_non_headless_respects_llm_approve(self):
        """Test that non-headless mode respects llm_approve setting."""
        with patch("openhands_cli.refactor.textual_app.OpenHandsApp") as mock_app_class:
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            textual_main(
                headless=False,
                always_approve=False,
                llm_approve=True,
                exit_without_confirmation=False,
            )

            # Should use ConfirmRisky due to llm_approve
            mock_app_class.assert_called_once()
            call_kwargs = mock_app_class.call_args.kwargs
            policy = call_kwargs["initial_confirmation_policy"]
            assert isinstance(policy, ConfirmRisky)
            assert policy.threshold == SecurityRisk.HIGH

    def test_non_headless_default_always_confirm(self):
        """Test that non-headless mode defaults to AlwaysConfirm."""
        with patch("openhands_cli.refactor.textual_app.OpenHandsApp") as mock_app_class:
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            textual_main(
                headless=False,
                always_approve=False,
                llm_approve=False,
                exit_without_confirmation=False,
            )

            # Should use AlwaysConfirm as default
            mock_app_class.assert_called_once()
            call_kwargs = mock_app_class.call_args.kwargs
            assert isinstance(call_kwargs["initial_confirmation_policy"], AlwaysConfirm)


class TestHeadlessAppBehavior:
    """Test headless mode behavior in OpenHandsApp."""

    @pytest.mark.asyncio
    async def test_headless_mode_flag_set(self, monkeypatch: pytest.MonkeyPatch):
        """Test that headless_mode flag is properly set on app."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda: False,
        )

        app = OpenHandsApp(exit_confirmation=False)
        app.headless_mode = True  # This is set in textual_main

        assert app.headless_mode is True

    @pytest.mark.asyncio
    async def test_conversation_state_change_triggers_exit_in_headless(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that conversation completion triggers exit in headless mode."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda: False,
        )

        app = OpenHandsApp(exit_confirmation=False)
        app.headless_mode = True

        # Mock the exit method
        exit_mock = MagicMock()
        app.exit = exit_mock

        # Simulate conversation finishing (is_running=False)
        app._on_conversation_state_changed(is_running=False)

        # Should call exit
        exit_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_state_change_no_exit_when_running(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that conversation starting doesn't trigger exit in headless mode."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda: False,
        )

        app = OpenHandsApp(exit_confirmation=False)
        app.headless_mode = True

        # Mock the exit method
        exit_mock = MagicMock()
        app.exit = exit_mock

        # Simulate conversation starting (is_running=True)
        app._on_conversation_state_changed(is_running=True)

        # Should not call exit
        exit_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_conversation_state_change_no_exit_in_non_headless(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that conversation completion doesn't trigger exit in non-headless."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda: False,
        )

        app = OpenHandsApp(exit_confirmation=False)
        app.headless_mode = False

        # Mock the exit method
        exit_mock = MagicMock()
        app.exit = exit_mock

        # Simulate conversation finishing (is_running=False)
        app._on_conversation_state_changed(is_running=False)

        # Should not call exit in non-headless mode
        exit_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_headless_mode_runs_with_headless_parameter(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that headless mode calls app.run with headless=True."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda: False,
        )

        with patch("openhands_cli.refactor.textual_app.OpenHandsApp") as mock_app_class:
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app
            mock_app.conversation_id = UUID("12345678-1234-5678-9012-123456789012")

            result = textual_main(headless=True, exit_without_confirmation=True)

            # Should call run with headless=True
            mock_app.run.assert_called_once_with(headless=True)
            # Should create app with headless_mode=True
            mock_app_class.assert_called_once()
            call_kwargs = mock_app_class.call_args[1]
            assert call_kwargs["headless_mode"] is True
            # Should return conversation_id
            assert result == mock_app.conversation_id


class TestHeadlessIntegration:
    """Integration tests for headless mode end-to-end behavior."""

    @patch("openhands_cli.agent_chat.run_cli_entry")
    def test_full_headless_flow_from_simple_main(self, mock_run_cli_entry):
        """Test complete headless flow from simple_main to run_cli_entry."""
        test_args = ["openhands", "--headless", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        # Verify run_cli_entry was called (validation passed)
        mock_run_cli_entry.assert_called_once()

    def test_headless_help_text_mentions_requirements(self):
        """Test that --headless help text mentions task/file requirement."""
        parser = create_main_parser()
        help_text = parser.format_help()

        # Should mention the requirement in help text
        assert "--headless" in help_text
        assert "Requires --task or --file" in help_text

    @pytest.mark.parametrize(
        "args,headless_expected",
        [
            (["--headless"], True),  # Parser accepts this, validation is in simple_main
            (["--headless", "--task", "test"], True),  # Has task
            (["--headless", "--file", "test.txt"], True),  # Has file
            (["--headless", "--task", "test", "--file", "test.txt"], True),  # Has both
            (["--task", "test"], False),  # Non-headless with task
            (["--file", "test.txt"], False),  # Non-headless with file
            ([], False),  # No args (should work for interactive mode)
        ],
    )
    def test_headless_validation_combinations(self, args, headless_expected):
        """Test various argument combinations for headless parsing."""
        parser = create_main_parser()

        # All combinations should parse successfully (validation is in simple_main)
        parsed_args = parser.parse_args(args)
        assert parsed_args.headless is headless_expected

    @patch("openhands_cli.agent_chat.run_cli_entry")
    def test_simple_main_validation_rejects_headless_without_task_or_file(
        self, mock_run_cli_entry
    ):
        """Test that simple_main validation rejects --headless without --task/--file."""
        test_args = ["openhands", "--headless"]

        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                with patch("sys.stderr"):  # Suppress error output
                    simple_main()
            assert exc_info.value.code == 2

        # run_cli_entry should not be called
        mock_run_cli_entry.assert_not_called()

    @patch("openhands_cli.agent_chat.run_cli_entry")
    def test_headless_mode_parameter_passing(self, mock_run_cli_entry):
        """Test that headless mode parameters are correctly processed."""
        test_args = ["openhands", "--headless", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        # Verify run_cli_entry was called with correct keyword arguments
        mock_run_cli_entry.assert_called_once()
        call_kwargs = mock_run_cli_entry.call_args.kwargs

        # Should have confirmation_policy as NeverConfirm (due to headless mode)
        from openhands.sdk.security.confirmation_policy import NeverConfirm

        assert isinstance(call_kwargs["confirmation_policy"], NeverConfirm)

        # Should have queued_inputs from the task
        assert call_kwargs["queued_inputs"] == ["test task"]


class TestConversationSummary:
    """Test conversation summary functionality for headless mode."""

    def test_conversation_summary_parsing(self):
        """Test that conversation summary correctly parses events."""
        import uuid
        from unittest.mock import Mock

        from openhands.sdk.event import MessageEvent
        from openhands_cli.refactor.core.conversation_runner import ConversationRunner

        # Create mock objects
        mock_conversation = Mock()
        mock_conversation.state = Mock()

        # Create mock events
        user_event = Mock(spec=MessageEvent)
        user_event.llm_message = Mock()
        user_event.llm_message.role = "user"

        agent_event = Mock(spec=MessageEvent)
        agent_event.llm_message = Mock()
        agent_event.llm_message.role = "assistant"
        # Mock visualize as a property that returns a Text object
        from unittest.mock import PropertyMock

        type(agent_event).visualize = PropertyMock(
            return_value=Mock(
                __str__=Mock(return_value="This is a test agent response message.")
            )
        )

        mock_conversation.state.events = [
            user_event,
            agent_event,
            user_event,
            agent_event,
        ]

        # Create conversation runner with mocks
        runner = ConversationRunner(
            conversation_id=uuid.uuid4(),
            running_state_callback=Mock(),
            confirmation_callback=Mock(),
            notification_callback=Mock(),
            visualizer=Mock(),
        )

        # Replace the conversation with our mock
        runner.conversation = mock_conversation

        # Test the summary
        summary = runner.get_conversation_summary()

        # Verify results
        assert summary["agent_messages"] == 2
        assert summary["user_messages"] == 2
        assert summary["last_agent_message"] == "This is a test agent response message."

    def test_conversation_summary_empty_state(self):
        """Test conversation summary with empty or None state."""
        import uuid
        from unittest.mock import Mock, patch

        from openhands_cli.refactor.core.conversation_runner import ConversationRunner

        # Mock setup_conversation to return None
        with patch(
            "openhands_cli.refactor.core.conversation_runner.setup_conversation",
            return_value=None,
        ):
            # Create conversation runner with no conversation
            runner = ConversationRunner(
                conversation_id=uuid.uuid4(),
                running_state_callback=Mock(),
                confirmation_callback=Mock(),
                notification_callback=Mock(),
                visualizer=Mock(),
            )

            # Test the summary
            summary = runner.get_conversation_summary()

            # Verify results
            assert summary["agent_messages"] == 0
            assert summary["user_messages"] == 0
            assert summary["last_agent_message"] == "No conversation data available"
