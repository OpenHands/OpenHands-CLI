"""Argument parser for cloud subcommand."""

import argparse
import os


def add_cloud_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add cloud subcommand parser.

    Args:
        subparsers: The subparsers object to add the cloud parser to

    Returns:
        The cloud argument parser
    """
    cloud_parser = subparsers.add_parser(
        "cloud", help="Create a new conversation in OpenHands Cloud"
    )

    # Task and file arguments (same as main parser)
    cloud_parser.add_argument(
        "-t",
        "--task",
        type=str,
        help="Initial task text to seed the conversation with",
    )

    cloud_parser.add_argument(
        "-f",
        "--file",
        type=str,
        help="Path to a file whose contents will seed the initial conversation",
    )

    # Server URL argument
    default_cloud_url = os.getenv("OPENHANDS_CLOUD_URL", "https://app.all-hands.dev")
    cloud_parser.add_argument(
        "--server-url",
        type=str,
        default=default_cloud_url,
        help=(
            f"OpenHands server URL for cloud operations (default: {default_cloud_url}, "
            "configurable via OPENHANDS_CLOUD_URL env var)"
        ),
    )

    return cloud_parser
