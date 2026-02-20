import argparse


def add_confirmation_mode_args(
    parser_or_group: argparse.ArgumentParser | argparse._MutuallyExclusiveGroup,
) -> None:
    """Add confirmation mode arguments to a parser or mutually exclusive group.

    Args:
        parser_or_group: Either an ArgumentParser or a mutually exclusive group
    """
    parser_or_group.add_argument(
        "--always-approve",
        "--yolo",
        action="store_true",
        help="Auto-approve all actions without asking for confirmation",
    )
    parser_or_group.add_argument(
        "--llm-approve",
        action="store_true",
        help=(
            "Enable LLM-based security analyzer "
            "(only confirm LLM-predicted high-risk actions)"
        ),
    )


def add_env_override_args(parser: argparse.ArgumentParser) -> None:
    """Add environment variable override arguments to a parser.

    Args:
        parser: The argument parser to add env override arguments to
    """
    parser.add_argument(
        "--override-with-envs",
        action="store_true",
        help=(
            "Override LLM settings with environment variables "
            "(LLM_API_KEY, LLM_BASE_URL, LLM_MODEL). "
            "By default, environment variables are ignored."
        ),
    )


def add_resume_args(parser: argparse.ArgumentParser) -> None:
    """Add resume-related arguments to a parser.

    Args:
        parser: The argument parser to add resume arguments to
    """
    parser.add_argument(
        "--resume",
        type=str,
        nargs="?",
        const="",
        help="Conversation ID to resume. If no ID provided, shows list of recent "
        "conversations",
    )
    parser.add_argument(
        "--last",
        action="store_true",
        help="Resume the most recent conversation (use with --resume)",
    )
