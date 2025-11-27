"""Main argument parser for OpenHands CLI."""

import argparse

from openhands_cli import __version__


def create_main_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with CLI as default and serve as subcommand.

    Returns:
        The configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="OpenHands CLI - Terminal User Interface for OpenHands AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            By default, OpenHands runs in CLI mode (terminal interface).
            Use 'serve' subcommand to launch the GUI server instead.

            Examples:
                openhands                           # Start CLI mode
                openhands --exp                     # Start experimental textual UI
                openhands --resume conversation-id  # Resume a conversation in CLI mode
                openhands serve                     # Launch GUI server
                openhands serve --gpu               # Launch GUI server with GPU support
                openhands acp                       # Start as Agent-Client Protocol
                                                      server for clients like Zed IDE
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
    parser.add_argument("--resume", type=str, help="Conversation ID to resume")
    parser.add_argument(
        "--exp",
        action="store_true",
        help="Use experimental textual-based UI instead of the default CLI interface",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Additional commands")

    # Add serve subcommand
    serve_parser = subparsers.add_parser(
        "serve", help="Launch the OpenHands GUI server using Docker (web interface)"
    )
    serve_parser.add_argument(
        "--mount-cwd",
        action="store_true",
        help="Mount the current working directory in the Docker container",
    )
    serve_parser.add_argument(
        "--gpu", action="store_true", help="Enable GPU support in the Docker container"
    )

    # Add ACP subcommand
    subparsers.add_parser(
        "acp", help="Start OpenHands as an Agent Client Protocol (ACP) agent"
    )

    return parser
