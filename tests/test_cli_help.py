from openhands_cli.argparsers.main_parser import create_main_parser


def test_main_help_includes_key_subcommands_and_flags() -> None:
    """Help text should mention serve, acp, and confirmation flags.

    This guards against accidental regressions in the CLI help/epilog.
    """
    parser = create_main_parser()
    help_text = parser.format_help()

    # Subcommands
    assert "serve" in help_text
    assert "acp" in help_text

    # Confirmation flags
    assert "--always-approve" in help_text
    assert "--llm-approve" in help_text

    # Version flag should also be advertised
    assert "--version" in help_text or "-v" in help_text
