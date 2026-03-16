"""Tests for headless mode and conversation summary behavior."""

import os
import sys
import tempfile
import uuid
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from rich.text import Text

from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.risk import SecurityRisk
from openhands_cli.argparsers.main_parser import create_main_parser
from openhands_cli.entrypoint import main as simple_main
from openhands_cli.tui.modals.settings.settings_screen import SettingsScreen
from openhands_cli.tui.textual_app import OpenHandsApp, main as textual_main


# ---------------------------------------------------------------------------
# Argument parsing / simple_main validation
# ---------------------------------------------------------------------------


class TestHeadlessArgumentParsing:
    """Minimal but high-impact coverage for headless arg parsing."""

    def test_headless_flag_parsed_and_default_false(self):
        parser = create_main_parser()

        # No flag -> False
        args = parser.parse_args(["--task", "test"])
        assert hasattr(args, "headless")
        assert args.headless is False

        # With flag -> True
        args = parser.parse_args(["--headless", "--task", "test"])
        assert args.headless is True

    def test_headless_can_be_parsed_without_task_or_file(self):
        """Parser itself accepts this; validation happens in simple_main."""
        parser = create_main_parser()
        args = parser.parse_args(["--headless"])
        assert args.headless is True
        assert args.task is None
        assert args.file is None


class TestSimpleMainHeadlessValidation:
    """High-level validation behavior of simple_main."""

    @patch("openhands_cli.tui.textual_app.main")
    def test_headless_without_task_or_file_exits_with_error(self, mock_textual_main):
        test_args = ["openhands", "--headless"]

        with patch.object(sys, "argv", test_args):
            with patch("sys.stderr"):  # suppress usage output
                with pytest.raises(SystemExit) as exc:
                    simple_main()
        assert exc.value.code == 2
        mock_textual_main.assert_not_called()

    @patch("openhands_cli.tui.textual_app.main")
    def test_headless_flag_passes_critic_disabled_true(self, mock_textual_main):
        """Test that --headless flag passes critic_disabled=True to textual_main."""
        # Mock textual_main to return a UUID
        mock_textual_main.return_value = uuid.uuid4()

        test_args = ["openhands", "--headless", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        # Verify textual_main was called with critic_disabled=True
        mock_textual_main.assert_called_once()
        kwargs = mock_textual_main.call_args.kwargs
        assert kwargs.get("critic_disabled") is True

    @patch("openhands_cli.tui.textual_app.main")
    def test_headless_with_override_envs_passes_both_params(self, mock_textual_main):
        """Test --headless --override-with-envs passes both params to textual_main."""
        # Mock textual_main to return a UUID
        mock_textual_main.return_value = uuid.uuid4()

        test_args = [
            "openhands",
            "--headless",
            "--override-with-envs",
            "--task",
            "test task",
        ]

        with patch.object(sys, "argv", test_args):
            simple_main()

        # Verify textual_main was called with both params set correctly
        mock_textual_main.assert_called_once()
        kwargs = mock_textual_main.call_args.kwargs
        assert kwargs.get("critic_disabled") is True
        assert kwargs.get("env_overrides_enabled") is True

    @patch("openhands_cli.tui.textual_app.main")
    def test_non_headless_passes_critic_disabled_false(self, mock_textual_main):
        """Test that without --headless, critic_disabled=False is passed."""
        # Mock textual_main to return a UUID
        mock_textual_main.return_value = uuid.uuid4()

        # Run without --headless flag
        test_args = ["openhands", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        # Verify textual_main was called with critic_disabled=False
        mock_textual_main.assert_called_once()
        kwargs = mock_textual_main.call_args.kwargs
        assert kwargs.get("critic_disabled") is False

    @patch("openhands_cli.tui.textual_app.main")
    def test_headless_with_task_calls_textual_main_with_queued_input(
        self, mock_textual_main
    ):
        # Mock textual_main to return a UUID
        mock_textual_main.return_value = uuid.uuid4()

        test_args = ["openhands", "--headless", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        mock_textual_main.assert_called_once()
        kwargs = mock_textual_main.call_args.kwargs

        # Headless should queue the task and set headless=True
        assert kwargs["queued_inputs"] == ["test task"]
        assert kwargs["headless"] is True

    @patch("openhands_cli.tui.textual_app.main")
    def test_headless_with_file_calls_textual_main(self, mock_textual_main):
        # Mock textual_main to return a UUID
        mock_textual_main.return_value = uuid.uuid4()

        # minimal coverage that file-only headless works
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("test content")
            temp_file = f.name

        try:
            test_args = ["openhands", "--headless", "--file", temp_file]
            with patch.object(sys, "argv", test_args):
                simple_main()

            mock_textual_main.assert_called_once()
        finally:
            os.unlink(temp_file)

    @patch("openhands_cli.tui.textual_app.main")
    def test_headless_auto_sets_exit_without_confirmation(self, mock_textual_main):
        """Regression guard that headless implies exit_without_confirmation."""
        # Mock textual_main to return a UUID
        mock_textual_main.return_value = uuid.uuid4()

        test_args = ["openhands", "--headless", "--task", "test task"]

        with patch.object(sys, "argv", test_args):
            simple_main()

        mock_textual_main.assert_called_once()
        kwargs = mock_textual_main.call_args.kwargs

        # Headless should auto-set exit_without_confirmation
        assert kwargs["exit_without_confirmation"] is True

    def test_headless_help_text_mentions_requirements(self):
        """Ensure CLI help describes the task/file requirement."""
        parser = create_main_parser()
        help_text = parser.format_help()
        assert "--headless" in help_text
        assert "Requires --task or --file" in help_text


# ---------------------------------------------------------------------------
# textual.main → confirmation policy wiring
# ---------------------------------------------------------------------------


class TestHeadlessConfirmationPolicy:
    """High-impact confirmation policy behavior for textual_main."""

    @pytest.mark.parametrize(
        "headless,always_approve,llm_approve,expected_type,expected_threshold",
        [
            # Headless forces NeverConfirm regardless of flags
            (True, False, False, NeverConfirm, None),
            (True, True, True, NeverConfirm, None),
            # Non-headless + always_approve -> NeverConfirm
            (False, True, False, NeverConfirm, None),
            # Non-headless + llm_approve -> ConfirmRisky(HIGH)
            (False, False, True, ConfirmRisky, SecurityRisk.HIGH),
            # Default non-headless -> AlwaysConfirm
            (False, False, False, AlwaysConfirm, None),
        ],
    )
    def test_confirmation_policy_selection(
        self,
        headless: bool,
        always_approve: bool,
        llm_approve: bool,
        expected_type,
        expected_threshold,
    ):
        with patch("openhands_cli.tui.textual_app.OpenHandsApp") as mock_app_cls:
            mock_app = MagicMock()
            mock_app_cls.return_value = mock_app

            textual_main(
                headless=headless,
                always_approve=always_approve,
                llm_approve=llm_approve,
                exit_without_confirmation=True,
            )

            mock_app_cls.assert_called_once()
            policy = mock_app_cls.call_args.kwargs["initial_confirmation_policy"]
            assert isinstance(policy, expected_type)
            if isinstance(policy, ConfirmRisky):
                assert policy.threshold == expected_threshold


# ---------------------------------------------------------------------------
# OpenHandsApp headless behavior + summary printing
# ---------------------------------------------------------------------------


class TestHeadlessAppBehavior:
    """Tests focused on headless flag and auto-exit behavior in OpenHandsApp.

    Note: Tests for _on_conversation_state_changed were removed as that method
    no longer exists. The headless exit behavior is now handled through
    ConversationContainer's watch_running and ConversationFinished message handling.
    """

    # Placeholder - add tests for ConversationContainer-based headless behavior
    pass


class TestPrintConversationSummary:
    """Focused tests for _print_conversation_summary."""

    def test_print_conversation_summary_no_runner_is_noop(self, monkeypatch):
        """If no conversation_runner is set, method should be a no-op (no crash)."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )
        app = OpenHandsApp(exit_confirmation=False)

        # Just ensure this doesn't raise
        app._print_conversation_summary()

    def test_print_conversation_summary_uses_console_and_state(self, monkeypatch):
        """Ensure we call state.get_conversation_summary and Console.print."""
        from rich.text import Text

        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        # Mock conversation_state.get_conversation_summary
        app.conversation_state.get_conversation_summary = MagicMock(
            return_value=(2, Text("Last agent message"))
        )

        with patch("rich.console.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            app._print_conversation_summary()

            app.conversation_state.get_conversation_summary.assert_called_once()
            assert mock_console.print.call_count >= 1


# ---------------------------------------------------------------------------
# ConversationRunner.get_conversation_summary behavior
# ---------------------------------------------------------------------------


class TestHeadlessRunnerOutput:
    """Tests for headless mode output without spinner."""

    def test_headless_mode_prints_status_without_spinner(self):
        """Test that headless mode prints status messages without spinner."""
        from openhands_cli.tui.core.conversation_runner import ConversationRunner
        from openhands_cli.tui.core.state import ConversationContainer

        mock_conversation = Mock()
        mock_conversation.send_message = Mock()
        mock_conversation.run = Mock()

        # Create mock state and message_pump
        mock_state = Mock(spec=ConversationContainer)
        mock_state.confirmation_policy = NeverConfirm()
        mock_state.attach_conversation = Mock()
        # Ensure is_confirmation_active returns False so headless path is taken
        mock_state.is_confirmation_active = False
        mock_message_pump = Mock()

        with patch(
            "openhands_cli.tui.core.conversation_runner.setup_conversation",
            return_value=mock_conversation,
        ):
            runner = ConversationRunner(
                conversation_id=uuid.uuid4(),
                state=mock_state,
                message_pump=mock_message_pump,
                notification_callback=Mock(),
                visualizer=Mock(),
            )

        message = Mock()

        with patch(
            "openhands_cli.tui.core.conversation_runner.Console"
        ) as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            runner._run_conversation_sync(message, headless=True)

            # Verify console.print was called with the expected messages
            print_calls = [call[0][0] for call in mock_console.print.call_args_list]
            assert "Agent is working" in print_calls
            assert "Agent finished" in print_calls

            # Verify console.status was NOT called (no spinner)
            mock_console.status.assert_not_called()


class TestConversationSummary:
    """Tests for ConversationRunner.get_conversation_summary itself."""

    def test_conversation_summary_parsing(self):
        """It should count agent messages and return last agent message text."""
        from openhands.sdk.event import MessageEvent
        from openhands_cli.tui.core.conversation_runner import ConversationRunner
        from openhands_cli.tui.core.state import ConversationContainer

        mock_conversation = Mock()
        mock_conversation.state = Mock()

        # Mock events
        user_event = Mock(spec=MessageEvent)
        user_event.llm_message = Mock()
        user_event.llm_message.role = "user"
        user_event.source = "user"

        agent_event = Mock(spec=MessageEvent)
        agent_event.llm_message = Mock()
        agent_event.llm_message.role = "assistant"
        agent_event.source = "agent"

        # visualize returns an object whose __str__ is the message text
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

        # Create mock state and message_pump
        mock_state = Mock(spec=ConversationContainer)
        mock_state.confirmation_policy = AlwaysConfirm()
        mock_state.attach_conversation = Mock()
        mock_message_pump = Mock()

        with patch(
            "openhands_cli.tui.core.conversation_runner.setup_conversation",
            return_value=mock_conversation,
        ):
            runner = ConversationRunner(
                conversation_id=uuid.uuid4(),
                state=mock_state,
                message_pump=mock_message_pump,
                notification_callback=Mock(),
                visualizer=Mock(),
            )

        agent_count, last_agent_message = runner.get_conversation_summary()
        assert agent_count == 2
        # We only care about what will be printed, not the concrete type
        assert str(last_agent_message) == "This is a test agent response message."

    def test_conversation_summary_empty_state(self):
        """With no conversation / events, we should get a safe default."""
        from openhands_cli.tui.core.conversation_runner import ConversationRunner
        from openhands_cli.tui.core.state import ConversationContainer

        # Create a mock ConversationContainer and message_pump
        mock_state = Mock(spec=ConversationContainer)
        mock_state.confirmation_policy = AlwaysConfirm()
        mock_state.attach_conversation = Mock()
        mock_message_pump = Mock()

        with patch(
            "openhands_cli.tui.core.conversation_runner.setup_conversation",
            return_value=None,
        ):
            runner = ConversationRunner(
                conversation_id=uuid.uuid4(),
                state=mock_state,
                message_pump=mock_message_pump,
                notification_callback=Mock(),
                visualizer=Mock(),
            )

        agent_count, last_agent_message = runner.get_conversation_summary()
        assert agent_count == 0

        # Again, expect a rich.Text object with the default message
        assert isinstance(last_agent_message, Text)
        assert str(last_agent_message) == "No conversation data available"


class TestHeadlessInitialSetupGuard:
    def test_headless_with_initial_setup_required_exits_and_instructs_user(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If settings aren't configured, headless mode
        should exit and print guidance."""
        # Pretend this is a fresh install / no settings
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: True,
        )

        app = OpenHandsApp(
            exit_confirmation=False,
            headless_mode=True,
            resume_conversation_id=uuid.uuid4(),
        )

        # We don't want to actually exit the process in the test
        app.exit = MagicMock()
        # Ensure the interactive path is not taken
        app._show_initial_settings = MagicMock()

        with patch("rich.console.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            app.on_mount()

            # Should exit immediately
            app.exit.assert_called_once()
            # Should NOT try to open the interactive settings screen
            app._show_initial_settings.assert_not_called()

            # We should have printed a message that mentions `openhands`
            printed_any_hint = any(
                "openhands" in str(arg)
                for call in mock_console.print.call_args_list
                for arg in call.args
            )
            assert printed_any_hint


# ---------------------------------------------------------------------------
# JSON Mode Tests (Minimal High-Impact Coverage)
# ---------------------------------------------------------------------------


class TestJsonArgumentValidation:
    """Minimal tests for JSON argument validation."""

    def test_json_requires_headless_mode(self):
        """Test that JSON flag requires headless mode."""
        # JSON without headless should not enable JSON mode
        with patch("openhands_cli.tui.textual_app.main") as mock_textual:
            # Mock sys.argv for argument parsing
            with patch("sys.argv", ["openhands", "--json", "--task", "test task"]):
                simple_main()

            # Verify textual_main was called with json_mode=False
            mock_textual.assert_called_once()
            args, kwargs = mock_textual.call_args
            assert kwargs.get("json_mode", False) is False

    def test_json_and_headless_enables_json_mode(self):
        """Test that JSON + headless enables JSON mode."""
        with patch("openhands_cli.tui.textual_app.main") as mock_textual:
            # Mock sys.argv for argument parsing
            with patch(
                "sys.argv", ["openhands", "--headless", "--json", "--task", "test task"]
            ):
                simple_main()

            # Verify textual_main was called with json_mode=True
            mock_textual.assert_called_once()
            args, kwargs = mock_textual.call_args
            assert kwargs.get("json_mode", False) is True


class TestJsonModeIntegration:
    """Minimal tests for JSON mode integration."""

    def test_json_callback_function_exists_and_callable(self):
        """Test that json_callback function exists and is callable."""
        from openhands_cli.utils import json_callback

        # Verify the function exists and is callable
        assert callable(json_callback)

        # Test that it can be used as an event callback (basic compatibility)
        from openhands.sdk.event import Event

        mock_event = Mock(spec=Event)
        mock_event.model_dump.return_value = {"test": "data"}

        # Should not raise an exception
        with patch("builtins.print"):
            json_callback(mock_event)


class TestMissingEnvVarsErrorHandling:
    """Tests for MissingEnvironmentVariablesError handling in entrypoint."""

    def test_missing_env_vars_error_prints_message_and_exits(self, capsys) -> None:
        """Test that MissingEnvironmentVariablesError prints message and exits."""
        from openhands_cli.stores import MissingEnvironmentVariablesError

        # Mock textual_main to raise MissingEnvironmentVariablesError
        # (simulating what happens when the app runs and AgentStore.load() fails)
        def raise_missing_env_vars(*args, **kwargs):
            raise MissingEnvironmentVariablesError(["LLM_API_KEY", "LLM_MODEL"])

        test_args = [
            "openhands",
            "--headless",
            "--override-with-envs",
            "--task",
            "test",
        ]

        with (
            patch.object(sys, "argv", test_args),
            patch(
                "openhands_cli.tui.textual_app.main", side_effect=raise_missing_env_vars
            ),
        ):
            with pytest.raises(SystemExit) as exc_info:
                simple_main()

            # Should exit with code 1
            assert exc_info.value.code == 1

            # Check that the error message was printed
            captured = capsys.readouterr()
            assert "LLM_API_KEY" in captured.out
            assert "LLM_MODEL" in captured.out
            assert "Missing required environment variable(s)" in captured.out
