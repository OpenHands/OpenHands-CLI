from openhands_cli.argparsers.main_parser import create_main_parser


def test_user_skills_default_true():
    parser = create_main_parser()
    args = parser.parse_args([])
    assert args.user_skills is True


def test_user_skills_disable_with_flag():
    parser = create_main_parser()
    args = parser.parse_args(["--no-user-skills"])
    assert args.user_skills is False
