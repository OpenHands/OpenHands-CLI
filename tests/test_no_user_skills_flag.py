from __future__ import annotations

from unittest.mock import MagicMock, patch

from openhands_cli.argparsers.main_parser import create_main_parser


def test_no_user_skills_flag_default_is_true():
    """Test that user_skills defaults to True when --no-user-skills is not provided."""
    parser = create_main_parser()
    args = parser.parse_args([])
    assert args.user_skills is True


def test_no_user_skills_flag_sets_false():
    """Test that --no-user-skills sets user_skills to False."""
    parser = create_main_parser()
    args = parser.parse_args(["--no-user-skills"])
    assert args.user_skills is False


def test_no_user_skills_flag_wires_through_to_textual_main():
    """Test that user_skills is passed through to textual_main."""

    # Mock the necessary dependencies
    mock_parser = MagicMock()
    mock_parser.parse_args.return_value = MagicMock(
        command=None,
        headless=False,
        json=False,
        task=None,
        file=None,
        resume=None,
        last=False,
        always_approve=False,
        llm_approve=False,
        exit_without_confirmation=False,
        override_with_envs=False,
        user_skills=False,  # This is what we're testing
    )

    with (
        patch(
            "openhands_cli.entrypoint.create_main_parser", return_value=mock_parser
        ),
        patch("openhands_cli.entrypoint.check_and_warn_env_vars"),
        patch(
            "openhands_cli.entrypoint.check_terminal_compatibility"
        ) as mock_compat,
        patch("openhands_cli.tui.textual_app.main") as mocked_textual_main,
    ):
        mock_compat.return_value = MagicMock(is_tty=True)
        mocked_textual_main.return_value = None

        from openhands_cli import entrypoint

        entrypoint.main()

        mocked_textual_main.assert_called_once()
        _, kwargs = mocked_textual_main.call_args
        assert kwargs["user_skills"] is False
