"""Tests for openhands_cli/setup.py."""

import uuid
from unittest.mock import MagicMock, patch

import pytest


class TestSetupConversationNoConsoleOutput:
    """setup_conversation must not print to stdout/stderr while the TUI is running.

    Console output from setup_conversation corrupts the Textual display because
    the function is called on the first user message, while the TUI is live.
    """

    def _make_mock_agent(self):
        agent = MagicMock()
        agent.llm = MagicMock()
        agent.llm.model = "test-model"
        return agent

    def _make_mock_conversation(self):
        conv = MagicMock()
        conv.set_security_analyzer = MagicMock()
        conv.set_confirmation_policy = MagicMock()
        return conv

    @pytest.fixture()
    def patched_setup(self):
        """Patch all I/O-touching dependencies of setup_conversation."""
        mock_agent = self._make_mock_agent()
        mock_conversation = self._make_mock_conversation()
        mock_hook_config = MagicMock()
        mock_hook_config.is_empty.return_value = False

        patches = {
            "load_agent_specs": patch(
                "openhands_cli.setup.load_agent_specs", return_value=mock_agent
            ),
            "HookConfig": patch(
                "openhands_cli.setup.HookConfig.load", return_value=mock_hook_config
            ),
            "Conversation": patch(
                "openhands_cli.setup.Conversation", return_value=mock_conversation
            ),
            "LLMSecurityAnalyzer": patch("openhands_cli.setup.LLMSecurityAnalyzer"),
            "get_work_dir": patch(
                "openhands_cli.setup.get_work_dir", return_value="/tmp/work"
            ),
            "get_conversations_dir": patch(
                "openhands_cli.setup.get_conversations_dir",
                return_value="/tmp/conversations",
            ),
        }
        started = {k: v.start() for k, v in patches.items()}
        yield started
        for p in patches.values():
            p.stop()

    def test_no_stdout_output(self, patched_setup, capsys):
        """setup_conversation must not write anything to stdout."""
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.setup import setup_conversation

        setup_conversation(
            conversation_id=uuid.uuid4(),
            confirmation_policy=NeverConfirm(),
        )

        captured = capsys.readouterr()
        assert captured.out == "", (
            f"setup_conversation wrote to stdout: {captured.out!r}"
        )

    def test_no_stderr_output(self, patched_setup, capsys):
        """setup_conversation must not write anything to stderr."""
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.setup import setup_conversation

        setup_conversation(
            conversation_id=uuid.uuid4(),
            confirmation_policy=NeverConfirm(),
        )

        captured = capsys.readouterr()
        assert captured.err == "", (
            f"setup_conversation wrote to stderr: {captured.err!r}"
        )

    def test_no_rich_console_print_called(self, patched_setup):
        """rich.console.Console.print must not be called during setup_conversation."""
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.setup import setup_conversation

        with patch("rich.console.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            setup_conversation(
                conversation_id=uuid.uuid4(),
                confirmation_policy=NeverConfirm(),
            )

        mock_console.print.assert_not_called()

    def test_returns_the_conversation_object(self, patched_setup):
        """setup_conversation must return the Conversation instance."""
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.setup import setup_conversation

        result = setup_conversation(
            conversation_id=uuid.uuid4(),
            confirmation_policy=NeverConfirm(),
        )

        # The mock Conversation() return value is what we expect back
        assert result is patched_setup["Conversation"].return_value
