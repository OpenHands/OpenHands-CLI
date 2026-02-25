import argparse
import os

from openhands_cli.argparsers.util import (
    add_confirmation_mode_args,
    add_env_override_args,
    add_resume_args,
)


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
    add_resume_args(acp_parser)

    # ACP confirmation mode options (mutually exclusive)
    acp_confirmation_group = acp_parser.add_mutually_exclusive_group()
    add_confirmation_mode_args(acp_confirmation_group)

    # Environment variable override option
    add_env_override_args(acp_parser)

    acp_parser.add_argument(
        "--cloud",
        action="store_true",
        default=False,
        help=(
            "Use OpenHands Cloud workspace instead of local workspace. "
            "Requires authentication via 'openhands login'."
        ),
    )

    # Cloud API URL (optional, defaults to production)
    acp_parser.add_argument(
        "--cloud-url",
        type=str,
        default=os.getenv("OPENHANDS_CLOUD_URL", "https://app.all-hands.dev"),
        help="OpenHands Cloud API URL",
    )

    # Debug logging option
    acp_parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging of ACP protocol messages to ~/.openhands/acp-debug/",
    )

    return acp_parser
