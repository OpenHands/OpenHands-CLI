"""Tests for main entry point functionality."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.risk import SecurityRisk
from openhands_cli import simple_main
from openhands_cli.argparsers.main_parser import create_main_parser
from openhands_cli.simple_main import main


def test_main_parser_accepts_task_and_file_flags():
    parser = create_main_parser()

    # --task only
    args = parser.parse_args(["--task", "do something"])
    assert args.task == "do something"
    assert args.file is None
    assert args.command is None  # no subcommand -> CLI mode

    # --file only
    args = parser.parse_args(["--file", "README.md"])
    assert args.file == "README.md"
    assert args.task is None

    # both
    args = parser.parse_args(["--task", "ignored", "--file", "README.md"])
    assert args.task == "ignored"
    assert args.file == "README.md"


class TestMainEntryPoint:
    """Test the main entry point behavior."""

    @patch("openhands_cli.agent_chat.run_cli_entry")
    @patch("sys.argv", ["openhands"])
    def test_main_starts_agent_chat_directly(
        self, mock_run_agent_chat: MagicMock
    ) -> None:
        """Test that main() starts agent chat directly when setup succeeds."""
        # Mock run_cli_entry to raise KeyboardInterrupt to exit gracefully
        mock_run_agent_chat.side_effect = KeyboardInterrupt()

        # Should complete without raising an exception (graceful exit)
        simple_main.main()

        # Should call run_cli_entry with no resume conversation ID,
        # AlwaysConfirm policy (default), and no queued inputs
        mock_run_agent_chat.assert_called_once()
        kwargs = mock_run_agent_chat.call_args.kwargs
        assert kwargs["resume_conversation_id"] is None
        assert isinstance(kwargs["confirmation_policy"], AlwaysConfirm)
        assert kwargs["queued_inputs"] is None

    @patch("openhands_cli.agent_chat.run_cli_entry")
    @patch("sys.argv", ["openhands"])
    def test_main_handles_import_error(self, mock_run_agent_chat: MagicMock) -> None:
        """Test that main() handles ImportError gracefully."""
        mock_run_agent_chat.side_effect = ImportError("Missing dependency")

        # Should raise ImportError (re-raised after handling)
        with pytest.raises(ImportError) as exc_info:
            simple_main.main()

        assert str(exc_info.value) == "Missing dependency"

    @patch("openhands_cli.agent_chat.run_cli_entry")
    @patch("sys.argv", ["openhands"])
    def test_main_handles_keyboard_interrupt(
        self, mock_run_agent_chat: MagicMock
    ) -> None:
        """Test that main() handles KeyboardInterrupt gracefully."""
        # Mock run_cli_entry to raise KeyboardInterrupt
        mock_run_agent_chat.side_effect = KeyboardInterrupt()

        # Should complete without raising an exception (graceful exit)
        simple_main.main()

    @patch("openhands_cli.agent_chat.run_cli_entry")
    @patch("sys.argv", ["openhands"])
    def test_main_handles_eof_error(self, mock_run_agent_chat: MagicMock) -> None:
        """Test that main() handles EOFError gracefully."""
        # Mock run_cli_entry to raise EOFError
        mock_run_agent_chat.side_effect = EOFError()

        # Should complete without raising an exception (graceful exit)
        simple_main.main()

    @patch("openhands_cli.agent_chat.run_cli_entry")
    @patch("sys.argv", ["openhands"])
    def test_main_handles_general_exception(
        self, mock_run_agent_chat: MagicMock
    ) -> None:
        """Test that main() handles general exceptions."""
        mock_run_agent_chat.side_effect = Exception("Unexpected error")

        # Should raise Exception (re-raised after handling)
        with pytest.raises(Exception) as exc_info:
            simple_main.main()

        assert str(exc_info.value) == "Unexpected error"

    @patch("openhands_cli.agent_chat.run_cli_entry")
    @patch("sys.argv", ["openhands", "--resume", "test-conversation-id"])
    def test_main_with_resume_argument(self, mock_run_agent_chat: MagicMock) -> None:
        """Test that main() passes resume conversation ID when provided."""
        # Mock run_cli_entry to raise KeyboardInterrupt to exit gracefully
        mock_run_agent_chat.side_effect = KeyboardInterrupt()

        # Should complete without raising an exception (graceful exit)
        simple_main.main()

        # Should call run_cli_entry with the provided resume conversation ID
        mock_run_agent_chat.assert_called_once()
        kwargs = mock_run_agent_chat.call_args.kwargs
        assert kwargs["resume_conversation_id"] == "test-conversation-id"
        assert isinstance(kwargs["confirmation_policy"], AlwaysConfirm)
        assert kwargs["queued_inputs"] is None

    @patch("openhands_cli.agent_chat.run_cli_entry")
    @patch("sys.argv", ["openhands", "--always-approve"])
    def test_main_with_always_approve_argument(
        self, mock_run_agent_chat: MagicMock
    ) -> None:
        """Test that main() passes NeverConfirm policy with --always-approve."""
        # Mock run_cli_entry to raise KeyboardInterrupt to exit gracefully
        mock_run_agent_chat.side_effect = KeyboardInterrupt()

        # Should complete without raising an exception (graceful exit)
        simple_main.main()

        # Should call run_cli_entry with NeverConfirm policy
        mock_run_agent_chat.assert_called_once()
        kwargs = mock_run_agent_chat.call_args.kwargs
        assert kwargs["resume_conversation_id"] is None
        assert isinstance(kwargs["confirmation_policy"], NeverConfirm)
        assert kwargs["queued_inputs"] is None

    @patch("openhands_cli.agent_chat.run_cli_entry")
    @patch("sys.argv", ["openhands", "--llm-approve"])
    def test_main_with_llm_approve_argument(
        self, mock_run_agent_chat: MagicMock
    ) -> None:
        """Test that main() passes ConfirmRisky policy with --llm-approve."""
        # Mock run_cli_entry to raise KeyboardInterrupt to exit gracefully
        mock_run_agent_chat.side_effect = KeyboardInterrupt()

        # Should complete without raising an exception (graceful exit)
        simple_main.main()

        # Should call run_cli_entry with ConfirmRisky policy
        mock_run_agent_chat.assert_called_once()
        kwargs = mock_run_agent_chat.call_args.kwargs
        assert kwargs["resume_conversation_id"] is None
        policy = kwargs["confirmation_policy"]
        assert isinstance(policy, ConfirmRisky)
        assert policy.threshold == SecurityRisk.HIGH
        assert kwargs["queued_inputs"] is None


@pytest.mark.parametrize(
    "argv,expected_resume_id,expected_policy_cls,expected_threshold",
    [
        (["openhands"], None, AlwaysConfirm, None),
        (["openhands", "--resume", "test-id"], "test-id", AlwaysConfirm, None),
        (["openhands", "--always-approve"], None, NeverConfirm, None),
        (
            ["openhands", "--llm-approve"],
            None,
            ConfirmRisky,
            SecurityRisk.HIGH,
        ),
        (
            ["openhands", "--resume", "test-id", "--always-approve"],
            "test-id",
            NeverConfirm,
            None,
        ),
    ],
)
def test_main_cli_calls_run_cli_entry(
    monkeypatch, argv, expected_resume_id, expected_policy_cls, expected_threshold
):
    # Patch sys.argv since main() takes no params
    monkeypatch.setattr(sys, "argv", argv, raising=False)

    called = {}
    fake_agent_chat = SimpleNamespace(
        run_cli_entry=lambda **kw: called.setdefault("kwargs", kw)
    )
    # Provide the symbol that main() will import
    monkeypatch.setitem(sys.modules, "openhands_cli.agent_chat", fake_agent_chat)

    # Execute (no SystemExit expected on success)
    main()
    kwargs = called["kwargs"]
    assert kwargs["resume_conversation_id"] == expected_resume_id
    assert isinstance(kwargs["confirmation_policy"], expected_policy_cls)
    if expected_threshold is not None:
        assert kwargs["confirmation_policy"].threshold == expected_threshold
    assert kwargs["queued_inputs"] is None


def test_main_cli_task_sets_queued_inputs(monkeypatch):
    """task should populate queued_inputs and not set resume_conversation_id."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["openhands", "--task", "Summarize the README"],
        raising=False,
    )

    called = {}

    fake_agent_chat = SimpleNamespace(
        run_cli_entry=lambda **kw: called.setdefault("kwargs", kw)
    )
    monkeypatch.setitem(sys.modules, "openhands_cli.agent_chat", fake_agent_chat)

    main()

    assert called["kwargs"]["resume_conversation_id"] is None
    assert called["kwargs"]["queued_inputs"] == ["Summarize the README"]


def test_main_cli_file_sets_queued_inputs(monkeypatch, tmp_path):
    """--file should build an queued_inputs with path + contents."""
    file_path = tmp_path / "context.txt"
    file_content = "Hello from test file"
    file_path.write_text(file_content, encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["openhands", "--file", str(file_path)],
        raising=False,
    )

    called = {}

    fake_agent_chat = SimpleNamespace(
        run_cli_entry=lambda **kw: called.setdefault("kwargs", kw)
    )
    monkeypatch.setitem(sys.modules, "openhands_cli.agent_chat", fake_agent_chat)

    main()

    assert called["kwargs"]["resume_conversation_id"] is None

    queued = called["kwargs"]["queued_inputs"]
    assert isinstance(queued, list)
    assert len(queued) == 1

    msg = queued[0]
    assert isinstance(msg, str)
    assert "Starting this session with file context." in msg
    assert f"File path: {file_path}" in msg
    assert file_content in msg


def test_main_cli_file_takes_precedence_over_task(monkeypatch, tmp_path):
    """When both task and file are provided, file should take precedence."""
    file_path = tmp_path / "context.txt"
    file_content = "Hello from file, not task"
    file_path.write_text(file_content, encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "openhands",
            "--task",
            "this should be ignored",
            "--file",
            str(file_path),
        ],
        raising=False,
    )

    called = {}

    fake_agent_chat = SimpleNamespace(
        run_cli_entry=lambda **kw: called.setdefault("kwargs", kw)
    )
    monkeypatch.setitem(sys.modules, "openhands_cli.agent_chat", fake_agent_chat)

    main()

    queued = called["kwargs"]["queued_inputs"]
    assert isinstance(queued, list)
    assert len(queued) == 1

    msg = queued[0]
    assert isinstance(msg, str)
    assert file_content in msg
    assert "this should be ignored" not in msg


@pytest.mark.parametrize(
    "argv,expected_kwargs",
    [
        (["openhands", "serve"], {"mount_cwd": False, "gpu": False}),
        (["openhands", "serve", "--mount-cwd"], {"mount_cwd": True, "gpu": False}),
        (["openhands", "serve", "--gpu"], {"mount_cwd": False, "gpu": True}),
        (
            ["openhands", "serve", "--mount-cwd", "--gpu"],
            {"mount_cwd": True, "gpu": True},
        ),
    ],
)
def test_main_serve_calls_launch_gui_server(monkeypatch, argv, expected_kwargs):
    monkeypatch.setattr(sys, "argv", argv, raising=False)

    called = {}
    fake_gui = SimpleNamespace(
        launch_gui_server=lambda **kw: called.setdefault("kwargs", kw)
    )
    monkeypatch.setitem(sys.modules, "openhands_cli.gui_launcher", fake_gui)

    main()
    assert called["kwargs"] == expected_kwargs


@pytest.mark.parametrize(
    "argv,expected_exit_code",
    [
        (["openhands", "invalid-command"], 2),  # argparse error
        (["openhands", "--help"], 0),  # top-level help
        (["openhands", "serve", "--help"], 0),  # subcommand help
        (
            ["openhands", "--always-approve", "--llm-approve"],
            2,
        ),  # mutually exclusive
    ],
)
def test_help_and_invalid(monkeypatch, argv, expected_exit_code):
    monkeypatch.setattr(sys, "argv", argv, raising=False)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == expected_exit_code


@pytest.mark.parametrize(
    "argv",
    [
        (["openhands", "--version"]),
        (["openhands", "-v"]),
    ],
)
def test_version_flag(monkeypatch, capsys, argv):
    """Test that --version and -v flags print version and exit."""
    monkeypatch.setattr(sys, "argv", argv, raising=False)

    with pytest.raises(SystemExit) as exc:
        main()

    # Version flag should exit with code 0
    assert exc.value.code == 0

    # Check that version string is in the output
    captured = capsys.readouterr()
    assert "OpenHands CLI" in captured.out
    # Should contain a version number (matches format like 1.2.1 or 0.0.0)
    import re

    assert re.search(r"\d+\.\d+\.\d+", captured.out)


def test_main_cloud_command_calls_handle_cloud_command(monkeypatch):
    """Test that cloud command calls handle_cloud_command function."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["openhands", "cloud", "--task", "Test task"],
        raising=False,
    )

    called = {}

    def mock_handle_cloud_command(args):
        called["args"] = args

    # Mock the handle_cloud_command function
    monkeypatch.setattr(
        "openhands_cli.cloud.command.handle_cloud_command", mock_handle_cloud_command
    )

    main()

    # Verify handle_cloud_command was called with correct args
    assert "args" in called
    args = called["args"]
    assert args.command == "cloud"
    assert args.task == "Test task"


def test_handle_cloud_command_with_task(monkeypatch):
    """Test handle_cloud_command function with task argument."""
    from unittest.mock import Mock, patch

    from openhands_cli.cloud.command import handle_cloud_command

    # Create mock args
    args = Mock()
    args.task = "Test task"
    args.file = None
    args.server_url = "https://test.com"

    # Mock the dependencies
    with patch(
        "openhands_cli.cloud.command.create_seeded_instructions_from_args"
    ) as mock_create_seeded:
        mock_create_seeded.return_value = ["Test task"]

        with patch("asyncio.run") as mock_asyncio_run:
            with patch("openhands_cli.cloud.command.console") as mock_console:
                handle_cloud_command(args)

                # Verify create_seeded_instructions_from_args was called
                mock_create_seeded.assert_called_once_with(args)

                # Verify asyncio.run was called
                mock_asyncio_run.assert_called_once()

                # Verify success message was printed
                success_calls = [
                    call
                    for call in mock_console.print.call_args_list
                    if "successfully" in str(call)
                ]
                assert len(success_calls) > 0


def test_handle_cloud_command_no_initial_message(monkeypatch):
    """Test handle_cloud_command function when no initial message is provided."""
    from unittest.mock import Mock, patch

    from openhands_cli.cloud.command import handle_cloud_command

    # Create mock args
    args = Mock()
    args.task = None
    args.file = None
    args.server_url = "https://test.com"

    # Mock the dependencies
    with patch(
        "openhands_cli.cloud.command.create_seeded_instructions_from_args"
    ) as mock_create_seeded:
        mock_create_seeded.return_value = []  # No initial message

        with patch("openhands_cli.cloud.command.console") as mock_console:
            handle_cloud_command(args)

            # Verify error message was printed
            error_calls = [
                call
                for call in mock_console.print.call_args_list
                if "Error: No initial message" in str(call)
            ]
            assert len(error_calls) > 0
