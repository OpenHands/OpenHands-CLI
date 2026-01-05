"""View command argument parser for OpenHands CLI."""

import argparse


def add_view_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the view subcommand parser.

    Args:
        subparsers: The subparsers action to add the view parser to
    """
    view_parser = subparsers.add_parser(
        "view",
        help="View the trajectory of an existing conversation",
        description="Display events from a conversation's trajectory",
    )

    view_parser.add_argument(
        "conversation_id",
        type=str,
        help="The conversation ID to view",
    )

    view_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=20,
        help="Maximum number of events to display (default: 20)",
    )
