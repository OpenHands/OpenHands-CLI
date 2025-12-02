"""Tests for CLI argument handling in the refactored UI."""

import uuid
from unittest.mock import MagicMock, patch

from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.risk import SecurityRisk
from openhands_cli.refactor.conversation_runner import ConversationRunner
from openhands_cli.refactor.textual_app import OpenHandsApp, main


class TestCLIArgsConfirmation:
    """Tests for CLI argument handling in confirmation policies."""

    def test_default_confirmation_policy(self):
        """Test that default behavior uses AlwaysConfirm policy."""
        app = OpenHandsApp()
        assert isinstance(app.initial_confirmation_policy, AlwaysConfirm)

    def test_never_confirm_policy(self):
        """Test that NeverConfirm policy is properly stored."""
        policy = NeverConfirm()
        app = OpenHandsApp(initial_confirmation_policy=policy)
        assert app.initial_confirmation_policy == policy

    def test_confirm_risky_policy(self):
        """Test that ConfirmRisky policy is properly stored."""
        policy = ConfirmRisky(threshold=SecurityRisk.HIGH)
        app = OpenHandsApp(initial_confirmation_policy=policy)
        assert app.initial_confirmation_policy == policy
        assert isinstance(app.initial_confirmation_policy, ConfirmRisky)
        assert app.initial_confirmation_policy.threshold == SecurityRisk.HIGH

    def test_always_confirm_policy(self):
        """Test that AlwaysConfirm policy is properly stored."""
        policy = AlwaysConfirm()
        app = OpenHandsApp(initial_confirmation_policy=policy)
        assert app.initial_confirmation_policy == policy

    @patch("openhands_cli.refactor.textual_app.TextualVisualizer")
    @patch("openhands_cli.refactor.textual_app.ConversationRunner")
    def test_conversation_runner_gets_never_confirm_policy(
        self, mock_runner_class, mock_visualizer_class
    ):
        """Test that NeverConfirm policy is passed to ConversationRunner."""
        policy = NeverConfirm()
        app = OpenHandsApp(initial_confirmation_policy=policy)

        # Mock the query_one method to return a mock main_display
        mock_main_display = MagicMock()
        app.query_one = MagicMock(return_value=mock_main_display)

        # Mock the conversation runner
        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner

        # Call on_mount to trigger conversation runner initialization
        app.on_mount()

        # Verify ConversationRunner was called with NeverConfirm policy
        mock_runner_class.assert_called_once()
        call_args = mock_runner_class.call_args

        # Check that the third argument (initial_confirmation_policy) is NeverConfirm
        assert len(call_args[0]) == 3  # conversation_id, visualizer, policy
        policy_arg = call_args[0][2]
        assert policy_arg == policy

    @patch("openhands_cli.refactor.textual_app.TextualVisualizer")
    @patch("openhands_cli.refactor.textual_app.ConversationRunner")
    def test_conversation_runner_gets_confirm_risky_policy(
        self, mock_runner_class, mock_visualizer_class
    ):
        """Test that ConfirmRisky policy is passed to ConversationRunner."""
        policy = ConfirmRisky(threshold=SecurityRisk.HIGH)
        app = OpenHandsApp(initial_confirmation_policy=policy)

        # Mock the query_one method to return a mock main_display
        mock_main_display = MagicMock()
        app.query_one = MagicMock(return_value=mock_main_display)

        # Mock the conversation runner
        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner

        # Call on_mount to trigger conversation runner initialization
        app.on_mount()

        # Verify ConversationRunner was called with ConfirmRisky policy
        mock_runner_class.assert_called_once()
        call_args = mock_runner_class.call_args

        # Check that the third argument (initial_confirmation_policy) is ConfirmRisky
        assert len(call_args[0]) == 3  # conversation_id, visualizer, policy
        policy_arg = call_args[0][2]
        assert policy_arg == policy

    @patch("openhands_cli.refactor.textual_app.TextualVisualizer")
    @patch("openhands_cli.refactor.textual_app.ConversationRunner")
    def test_conversation_runner_gets_default_always_confirm_policy(
        self, mock_runner_class, mock_visualizer_class
    ):
        """Test that default behavior results in AlwaysConfirm policy."""
        app = OpenHandsApp()

        # Mock the query_one method to return a mock main_display
        mock_main_display = MagicMock()
        app.query_one = MagicMock(return_value=mock_main_display)

        # Mock the conversation runner
        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner

        # Call on_mount to trigger conversation runner initialization
        app.on_mount()

        # Verify ConversationRunner was called with AlwaysConfirm policy
        mock_runner_class.assert_called_once()
        call_args = mock_runner_class.call_args

        # Check that the third argument (initial_confirmation_policy) is AlwaysConfirm
        assert len(call_args[0]) == 3  # conversation_id, visualizer, policy
        policy_arg = call_args[0][2]
        assert isinstance(policy_arg, AlwaysConfirm)


class TestConversationRunnerInitialPolicy:
    """Tests for ConversationRunner initial policy handling."""

    def test_conversation_runner_with_never_confirm_policy(self):
        """Test ConversationRunner initialization with NeverConfirm policy."""
        conversation_id = uuid.uuid4()
        policy = NeverConfirm()

        runner = ConversationRunner(
            conversation_id, None, initial_confirmation_policy=policy
        )

        assert runner.initial_confirmation_policy == policy
        assert runner.is_confirmation_mode_active is False

    def test_conversation_runner_with_confirm_risky_policy(self):
        """Test ConversationRunner initialization with ConfirmRisky policy."""
        conversation_id = uuid.uuid4()
        policy = ConfirmRisky(threshold=SecurityRisk.HIGH)

        runner = ConversationRunner(
            conversation_id, None, initial_confirmation_policy=policy
        )

        assert runner.initial_confirmation_policy == policy
        assert runner.is_confirmation_mode_active is True

    def test_conversation_runner_with_always_confirm_policy(self):
        """Test ConversationRunner initialization with AlwaysConfirm policy."""
        conversation_id = uuid.uuid4()
        policy = AlwaysConfirm()

        runner = ConversationRunner(
            conversation_id, None, initial_confirmation_policy=policy
        )

        assert runner.initial_confirmation_policy == policy
        assert runner.is_confirmation_mode_active is True

    def test_conversation_runner_default_policy(self):
        """Test ConversationRunner initialization with default policy."""
        conversation_id = uuid.uuid4()

        runner = ConversationRunner(conversation_id, None)

        assert isinstance(runner.initial_confirmation_policy, AlwaysConfirm)
        assert runner.is_confirmation_mode_active is True


class TestMainFunctionArgs:
    """Tests for the main function argument handling."""

    @patch("openhands_cli.refactor.textual_app.OpenHandsApp")
    def test_main_function_passes_never_confirm_policy(self, mock_app_class):
        """Test main function creates NeverConfirm policy for always_approve=True."""
        mock_app = MagicMock()
        mock_app_class.return_value = mock_app
        mock_app.conversation_id = uuid.uuid4()

        main(always_approve=True)

        # Verify OpenHandsApp was called with NeverConfirm policy
        mock_app_class.assert_called_once()
        call_kwargs = mock_app_class.call_args[1]
        policy = call_kwargs["initial_confirmation_policy"]
        assert isinstance(policy, NeverConfirm)

    @patch("openhands_cli.refactor.textual_app.OpenHandsApp")
    def test_main_function_passes_confirm_risky_policy(self, mock_app_class):
        """Test main function creates ConfirmRisky policy for llm_approve=True."""
        mock_app = MagicMock()
        mock_app_class.return_value = mock_app
        mock_app.conversation_id = uuid.uuid4()

        main(llm_approve=True)

        # Verify OpenHandsApp was called with ConfirmRisky policy
        mock_app_class.assert_called_once()
        call_kwargs = mock_app_class.call_args[1]
        policy = call_kwargs["initial_confirmation_policy"]
        assert isinstance(policy, ConfirmRisky)
        assert policy.threshold == SecurityRisk.HIGH

    @patch("openhands_cli.refactor.textual_app.OpenHandsApp")
    def test_main_function_default_args(self, mock_app_class):
        """Test main function uses AlwaysConfirm policy by default."""
        mock_app = MagicMock()
        mock_app_class.return_value = mock_app
        mock_app.conversation_id = uuid.uuid4()

        main()

        # Verify OpenHandsApp was called with AlwaysConfirm policy
        mock_app_class.assert_called_once()
        call_kwargs = mock_app_class.call_args[1]
        policy = call_kwargs["initial_confirmation_policy"]
        assert isinstance(policy, AlwaysConfirm)
