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
            By default, OpenHands runs in CLI mode (terminal interface)
            with 'always-ask' confirmation mode, where all agent actions
            require user confirmation.

            In headless mode the CLI auto-approves actions unless you
            explicitly select a different confirmation policy.

            Use 'serve' subcommand to launch the GUI server instead.

            Examples:
                openhands                           # Start CLI mode
                openhands --resume conversation-id  # Resume conversation
                openhands --always-approve          # Auto-approve all actions
                openhands --llm-approve             # LLM-based approval mode
                openhands --headless -t "do X"      # Run once in non-interactive mode
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

    parser.add_argument(
        "--headless",
        action="store_true",
        help=(
            "Run in non-interactive mode and exit automatically when the agent "
            "finishes (auto-approves actions unless another confirmation policy is set)"
        ),
    )

    # CLI arguments at top level (default mode)
    parser.add_argument("--resume", type=str, help="Conversation ID to resume")

    # Confirmation mode options (mutually exclusive)
    confirmation_group = parser.add_mutually_exclusive_group()
    confirmation_group.add_argument(
        "--always-approve",
        action="store_true",
        help="Auto-approve all actions without asking for confirmation",
    )
    confirmation_group.add_argument(
        "--llm-approve",
        action="store_true",
        help=(
            "Enable LLM-based security analyzer "
            "(only confirm LLM-predicted high-risk actions)"
        ),
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
