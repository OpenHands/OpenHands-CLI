import argparse

from openhands_cli.stores.cli_settings import DEFAULT_CRITIC_THRESHOLD


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


def add_iterative_refinement_args(parser: argparse.ArgumentParser) -> None:
    """Add iterative refinement arguments to a parser.

    Args:
        parser: The argument parser to add iterative refinement arguments to
    """
    parser.add_argument(
        "--iterative-refinement",
        action="store_true",
        help=(
            "Enable iterative refinement mode. When the critic model predicts "
            "task success probability below the threshold, a message is sent "
            "to the agent to review and improve its work."
        ),
    )
    parser.add_argument(
        "--critic-threshold",
        type=float,
        default=DEFAULT_CRITIC_THRESHOLD,
        help=(
            f"Critic score threshold for iterative refinement (0.0-1.0). "
            f"Default: {DEFAULT_CRITIC_THRESHOLD}. "
            "Refinement is triggered when score is below this threshold."
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
