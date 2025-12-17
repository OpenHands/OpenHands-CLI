"""Tests for cloud subcommand argument parsing."""

from unittest.mock import patch

import pytest

from openhands_cli.argparsers.main_parser import create_main_parser


def test_cloud_subcommand_with_task():
    """Test cloud subcommand with --task argument."""
    parser = create_main_parser()
    args = parser.parse_args(["cloud", "--task", "Fix the bug"])

    assert args.command == "cloud"
    assert args.task == "Fix the bug"
    assert args.file is None
    assert args.server_url == "https://app.all-hands.dev"


def test_cloud_subcommand_with_file():
    """Test cloud subcommand with --file argument."""
    parser = create_main_parser()
    args = parser.parse_args(["cloud", "--file", "task.txt"])

    assert args.command == "cloud"
    assert args.task is None
    assert args.file == "task.txt"
    assert args.server_url == "https://app.all-hands.dev"


def test_cloud_subcommand_with_custom_server_url():
    """Test cloud subcommand with custom server URL."""
    parser = create_main_parser()
    args = parser.parse_args(
        ["cloud", "--task", "Review code", "--server-url", "https://custom.example.com"]
    )

    assert args.command == "cloud"
    assert args.task == "Review code"
    assert args.server_url == "https://custom.example.com"


def test_cloud_subcommand_short_flags():
    """Test cloud subcommand with short flags."""
    parser = create_main_parser()
    args = parser.parse_args(["cloud", "-t", "Fix bug", "-f", "task.txt"])

    assert args.command == "cloud"
    assert args.task == "Fix bug"
    assert args.file == "task.txt"


def test_cloud_subcommand_with_env_var():
    """Test cloud subcommand respects OPENHANDS_CLOUD_URL environment variable."""
    with patch.dict("os.environ", {"OPENHANDS_CLOUD_URL": "https://env.example.com"}):
        parser = create_main_parser()
        args = parser.parse_args(["cloud", "--task", "Test task"])

        assert args.server_url == "https://env.example.com"


def test_cloud_subcommand_help():
    """Test that cloud subcommand help works."""
    parser = create_main_parser()

    # This should not raise an exception
    with pytest.raises(SystemExit):
        parser.parse_args(["cloud", "--help"])


def test_main_parser_still_works():
    """Test that main parser functionality is not broken."""
    parser = create_main_parser()

    # Test regular CLI mode
    args = parser.parse_args(["--task", "Regular task"])
    assert args.command is None
    assert args.task == "Regular task"

    # Test other subcommands still work
    args = parser.parse_args(["serve"])
    assert args.command == "serve"

    args = parser.parse_args(["login"])
    assert args.command == "login"
