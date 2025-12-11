"""Main argument parser for OpenHands CLI."""

import argparse
import sys

from openhands_cli import __version__
from openhands_cli.argparsers.mcp_parser import add_mcp_parser
from openhands_cli.argparsers.serve_parser import add_serve_parser


def preprocess_mcp_args(args: list[str]) -> list[str]:
    """Preprocess MCP arguments to handle -- separator correctly.

    This function handles the case where MCP add commands use -- to separate
    the command arguments, but argparse doesn't handle this well when optional
    arguments come after positional arguments.

    Args:
        args: List of command line arguments

    Returns:
        Preprocessed list of arguments
    """
    # Only process if this is an MCP add command with --
    if len(args) < 3 or args[0] != "mcp" or args[1] != "add" or "--" not in args:
        return args

    try:
        # Find the -- separator
        separator_index = args.index("--")

        # Split arguments at the -- separator
        before_separator = args[:separator_index]
        after_separator = args[separator_index + 1 :]  # Skip the -- itself

        # Find positional arguments (name and target)
        # They should be the first non-option arguments after "mcp add"
        positional_args = []
        option_args = []

        i = 2  # Start after "mcp add"
        while i < len(before_separator):
            arg = before_separator[i]
            if arg.startswith("--"):
                # This is an option, add it and its value
                option_args.append(arg)
                if i + 1 < len(before_separator) and not before_separator[
                    i + 1
                ].startswith("--"):
                    option_args.append(before_separator[i + 1])
                    i += 2
                else:
                    i += 1
            else:
                # This is a positional argument
                positional_args.append(arg)
                i += 1

        # Reconstruct the arguments in the correct order:
        # mcp add [options] name target [-- args...]
        result = ["mcp", "add"] + option_args + positional_args
        if after_separator:
            result.extend(["--"] + after_separator)

        return result

    except (ValueError, IndexError):
        # If anything goes wrong, return original args
        return args


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


class MainArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser that preprocesses MCP arguments."""

    def parse_args(self, args=None, namespace=None):  # type: ignore[override]
        """Parse arguments with MCP preprocessing."""
        if args is None:
            args = sys.argv[1:]

        # Convert to list for preprocessing
        args_list = list(args)

        # Preprocess MCP arguments
        processed_args = preprocess_mcp_args(args_list)

        return super().parse_args(processed_args, namespace)

    def parse_known_args(self, args=None, namespace=None):  # type: ignore[override]
        """Parse known arguments with MCP preprocessing."""
        if args is None:
            args = sys.argv[1:]

        # Convert to list for preprocessing
        args_list = list(args)

        # Preprocess MCP arguments
        processed_args = preprocess_mcp_args(args_list)

        return super().parse_known_args(processed_args, namespace)


def create_main_parser() -> MainArgumentParser:
    """Create the main argument parser with CLI as default and serve as subcommand.

    Returns:
        The configured argument parser
    """
    parser = MainArgumentParser(
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
    parser.add_argument("--resume", type=str, help="Conversation ID to resume")
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
