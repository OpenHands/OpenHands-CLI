import argparse

from openhands_cli.argparsers.util import add_confirmation_mode_args


def add_acp_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    # Add ACP subcommand
    acp_parser = subparsers.add_parser(
        "acp",
        help=(
            "Start OpenHands as an Agent Client Protocol (ACP) agent "
            "(e.g., Toad CLI, Zed IDE)"
        ),
    )

    # Resume arguments (same as main parser)
    acp_parser.add_argument(
        "--resume",
        type=str,
        nargs="?",
        const="",
        help="Conversation ID to resume. If no ID provided, shows list of recent "
        "conversations",
    )
    acp_parser.add_argument(
        "--last",
        action="store_true",
        help="Resume the most recent conversation (use with --resume)",
    )

    # ACP confirmation mode options (mutually exclusive)
    acp_confirmation_group = acp_parser.add_mutually_exclusive_group()
    add_confirmation_mode_args(acp_confirmation_group)

    return acp_parser
