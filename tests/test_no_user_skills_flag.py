from __future__ import annotations

from unittest.mock import patch

from openhands_cli.argparsers.main_parser import create_main_parser


def test_no_user_skills_flag_wires_through_to_agent_setup():
    parser = create_main_parser()
    args = parser.parse_args(["--no-user-skills"])
    assert args.user_skills is False

    with patch("openhands_cli.refactor.textual_app.main") as mocked_textual_main:
        mocked_textual_main.return_value = object()

        from openhands_cli.simple_main import main

        with patch.object(
            parser,
            "parse_args",
            return_value=args,
        ):
            main()

        mocked_textual_main.assert_called_once()
        _, kwargs = mocked_textual_main.call_args
        assert kwargs["user_skills"] is False
