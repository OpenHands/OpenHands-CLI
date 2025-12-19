from __future__ import annotations

from unittest.mock import patch, MagicMock

from openhands_cli.argparsers.main_parser import create_main_parser
from openhands_cli.agent_chat import run_cli_entry


def test_no_user_skills_flag_wires_through_to_agent_setup():
    parser = create_main_parser()
    args = parser.parse_args(["--no-user-skills"])
    assert args.user_skills is False

    # Patch verify_agent_exists_or_setup_agent because run_cli_entry calls it.
    with patch("openhands_cli.agent_chat.verify_agent_exists_or_setup_agent") as mocked_verify:
        mocked_agent = MagicMock()
        mocked_verify.return_value = mocked_agent

        run_cli_entry(user_skills=args.user_skills)

        mocked_verify.assert_called_once()
        _, kwargs = mocked_verify.call_args
        assert kwargs["user_skills"] is False
