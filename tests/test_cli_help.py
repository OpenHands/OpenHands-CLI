from openhands_cli.argparsers.main_parser import create_main_parser


def test_main_help_includes_key_subcommands_and_flags() -> None:
    """Help text should mention serve, acp, view, and confirmation flags.

    This guards against accidental regressions in the CLI help/epilog.
    """
    parser = create_main_parser()
    help_text = parser.format_help()

    # Subcommands
    assert "serve" in help_text
    assert "acp" in help_text
    assert "view" in help_text

    # Confirmation flags
    assert "--always-approve" in help_text
    assert "--llm-approve" in help_text

    # Version flag should also be advertised
    assert "--version" in help_text or "-v" in help_text


def test_acp_subcommand_supports_resume_flags() -> None:
    """ACP subcommand should support --resume and --last flags.

    This tests the fix for issue #260 where 'openhands acp --resume --last'
    was failing because the ACP parser didn't recognize these arguments.
    """
    parser = create_main_parser()

    # Test parsing 'acp --resume --last'
    args = parser.parse_args(["acp", "--resume", "--last"])
    assert args.command == "acp"
    assert args.resume == ""  # --resume without value gives empty string
    assert args.last is True

    # Test parsing 'acp --resume <conversation_id>'
    args = parser.parse_args(
        ["acp", "--resume", "12345678-1234-1234-1234-123456789abc"]
    )
    assert args.command == "acp"
    assert args.resume == "12345678-1234-1234-1234-123456789abc"
    assert args.last is False

    # Test parsing 'acp' without resume flags
    args = parser.parse_args(["acp"])
    assert args.command == "acp"
    assert args.resume is None
    assert args.last is False

    # Test parsing 'acp --llm-approve --resume --last'
    args = parser.parse_args(["acp", "--llm-approve", "--resume", "--last"])
    assert args.command == "acp"
    assert args.llm_approve is True
    assert args.resume == ""
    assert args.last is True


def test_view_subcommand_parses_correctly() -> None:
    """View subcommand should parse conversation_id and --limit correctly.

    This tests the view command for viewing conversation trajectories.
    """
    parser = create_main_parser()

    # Test parsing 'view <conversation_id>'
    args = parser.parse_args(["view", "test-conversation-id"])
    assert args.command == "view"
    assert args.conversation_id == "test-conversation-id"
    assert args.limit == 20  # default value

    # Test parsing 'view <conversation_id> --limit 10'
    args = parser.parse_args(["view", "test-conversation-id", "--limit", "10"])
    assert args.command == "view"
    assert args.conversation_id == "test-conversation-id"
    assert args.limit == 10

    # Test parsing 'view <conversation_id> -l 5'
    args = parser.parse_args(["view", "test-conversation-id", "-l", "5"])
    assert args.command == "view"
    assert args.conversation_id == "test-conversation-id"
    assert args.limit == 5
