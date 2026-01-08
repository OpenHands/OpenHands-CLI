"""Argument parser for authentication subcommands."""

import argparse
import os


def add_login_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add login subcommand parser.

    Args:
        subparsers: The subparsers object to add the login parser to

    Returns:
        The login argument parser
    """
    login_parser = subparsers.add_parser(
        "login", help="Authenticate with OpenHands Cloud using OAuth 2.0 Device Flow"
    )
    default_cloud_url = os.getenv("OPENHANDS_CLOUD_URL", "https://app.all-hands.dev")
    login_parser.add_argument(
        "--server-url",
        type=str,
        default=default_cloud_url,
        help=(
            f"OpenHands server URL (default: {default_cloud_url}, "
            "configurable via OPENHANDS_CLOUD_URL env var)"
        ),
    )
    return login_parser


def add_logout_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Add logout subcommand parser.

    Args:
        subparsers: The subparsers object to add the logout parser to

    Returns:
        The logout argument parser
    """
    logout_parser = subparsers.add_parser("logout", help="Log out from OpenHands Cloud")
    logout_parser.add_argument(
        "--server-url",
        type=str,
        help=(
            "OpenHands server URL to log out from "
            "(if not specified, logs out from all servers)"
        ),
    )
    return logout_parser
