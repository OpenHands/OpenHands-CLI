"""Argument parser for web subcommand."""

import argparse


def add_web_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add web subcommand parser.

    Args:
        subparsers: The subparsers object to add the web parser to

    Returns:
        The web argument parser
    """
    web_parser = subparsers.add_parser(
        "web", help="Launch the OpenHands CLI as a web application (browser interface)"
    )
    web_parser.add_argument(
        "--host",
        help="Host to bind the web server to",
        default="0.0.0.0",
        type=str,
    )
    web_parser.add_argument(
        "--port",
        help="Port to bind the web server to",
        default=12000,
        type=int,
    )
    web_parser.add_argument(
        "--debug",
        help="Enable debug mode for the web server",
        action="store_true",
        default=False,
    )
    return web_parser
