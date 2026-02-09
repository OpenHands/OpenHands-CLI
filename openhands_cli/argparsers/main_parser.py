"""Main argument parser for OpenHands CLI."""

import argparse

from openhands_cli import __version__
from openhands_cli.argparsers.acp_parser import add_acp_parser
from openhands_cli.argparsers.auth_parser import add_login_parser, add_logout_parser
from openhands_cli.argparsers.cloud_parser import add_cloud_parser
from openhands_cli.argparsers.mcp_parser import add_mcp_parser
from openhands_cli.argparsers.serve_parser import add_serve_parser
from openhands_cli.argparsers.util import (
    add_confirmation_mode_args,
    add_env_override_args,
    add_resume_args,
)
from openhands_cli.argparsers.view_parser import add_view_parser
from openhands_cli.argparsers.web_parser import add_web_parser


def create_main_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with CLI as default and serve as subcommand.

    Returns:
        The configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="OpenHands CLI - Terminal User Interface for OpenHands AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            By default, OpenHands runs in textual UI mode (terminal interface)
            with 'always-ask' confirmation mode, where all agent actions
            require user confirmation.

            Use 'serve' subcommand to launch the GUI server instead.

            Examples:
                openhands                           # Start textual UI mode
                openhands --headless                # Start textual UI in headless mode
                openhands --headless --json -t "Fix bug"  # Headless with JSON output
                openhands --resume conversation-id  # Resume conversation
                openhands --yolo                    # Auto-approve all actions
                openhands --llm-approve             # LLM-based approval mode
                openhands cloud -t "Fix bug"        # Create cloud conversation
                openhands serve                     # Launch GUI server
                openhands serve --gpu               # Launch with GPU support
                openhands web                       # Launch CLI as web app
                openhands web --port 8080           # Launch web app on custom port
                openhands acp                       # Agent-Client Protocol
                                                      server (e.g., Toad CLI, Zed IDE)
                openhands login                     # Authenticate with OpenHands Cloud
                openhands logout                    # Log out from OpenHands Cloud
        """,
    )

    # Version argument
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"OpenHands CLI {__version__}",
        help="Show the version number and exit",
    )

    parser.add_argument(
        "-t",
        "--task",
        type=str,
        help="Initial task text to seed the conversation with",
    )

    parser.add_argument(
        "-f",
        "--file",
        type=str,
        help="Path to a file whose contents will seed the initial conversation",
    )

    # CLI arguments at top level (default mode)
    add_resume_args(parser)
    parser.add_argument(
        "--headless",
        action="store_true",
        help=(
            "Run in headless mode (no UI output, auto-approve actions). "
            "Requires --task or --file."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Enable JSON output mode for headless operation. "
            "Streams JSONL event outputs to terminal. Must be used with --headless."
        ),
    )

    # Confirmation mode options (mutually exclusive)
    confirmation_group = parser.add_mutually_exclusive_group()
    add_confirmation_mode_args(confirmation_group)

    parser.add_argument(
        "--exit-without-confirmation",
        action="store_true",
        help="Exit the application without showing confirmation dialog",
    )

    # Environment variable override option
    add_env_override_args(parser)

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Additional commands")

    # Add acp subcommands
    add_acp_parser(subparsers)

    # Add serve subcommand
    add_serve_parser(subparsers)

    # Add web subcommand
    add_web_parser(subparsers)

    # Add MCP subcommand
    add_mcp_parser(subparsers)

    # Add cloud subcommand
    add_cloud_parser(subparsers)

    # Add authentication subcommands
    add_login_parser(subparsers)
    add_logout_parser(subparsers)

    # Add view subcommand
    add_view_parser(subparsers)

    return parser
