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

    # ACP confirmation mode options (mutually exclusive)
    acp_confirmation_group = acp_parser.add_mutually_exclusive_group()
    add_confirmation_mode_args(acp_confirmation_group)

    return acp_parser
