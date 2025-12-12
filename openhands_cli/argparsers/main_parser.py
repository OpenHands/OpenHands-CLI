"""Main argument parser for OpenHands CLI."""

import argparse

from openhands_cli import __version__
from openhands_cli.argparsers.mcp_parser import add_mcp_parser
from openhands_cli.argparsers.serve_parser import add_serve_parser


def add_confirmation_mode_args(
    parser_or_group: argparse.ArgumentParser | argparse._MutuallyExclusiveGroup,
) -> None:
    """Add confirmation mode arguments to a parser or mutually exclusive group.

    Args:
        parser_or_group: Either an ArgumentParser or a mutually exclusive group
    """
    parser_or_group.add_argument(
        "--always-approve",
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


def create_main_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with CLI as default and serve as subcommand.

    Returns:
        The configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="OpenHands CLI - Terminal User Interface for OpenHands AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            By default, OpenHands runs in CLI mode (terminal interface)
            with 'always-ask' confirmation mode, where all agent actions
            require user confirmation.

            Use 'serve' subcommand to launch the GUI server instead.

            Examples:
                openhands                           # Start CLI mode
                openhands --exp                     # Start experimental textual UI
                openhands --exp --headless          # Start textual UI in headless mode
                openhands --resume conversation-id  # Resume conversation
                openhands --always-approve          # Auto-approve all actions
                openhands --llm-approve             # LLM-based approval mode
                openhands serve                     # Launch GUI server
                openhands serve --gpu               # Launch with GPU support
                openhands acp                       # Agent-Client Protocol
                                                      server (e.g., Zed IDE)
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
    parser.add_argument(
        "--exp",
        action="store_true",
        help="Use experimental textual-based UI instead of the default CLI interface",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help=(
            "Run in headless mode (no UI output, auto-approve actions). "
            "Requires --task or --file."
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

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Additional commands")

    # Add serve subcommand
    add_serve_parser(subparsers)

    # Add ACP subcommand
    acp_parser = subparsers.add_parser(
        "acp", help="Start OpenHands as an Agent Client Protocol (ACP) agent"
    )

    # ACP confirmation mode options (mutually exclusive)
    acp_confirmation_group = acp_parser.add_mutually_exclusive_group()
    add_confirmation_mode_args(acp_confirmation_group)

    # Add MCP subcommand
    add_mcp_parser(subparsers)

    return parser
