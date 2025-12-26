#!/usr/bin/env python3
"""
Simple main entry point for OpenHands CLI.
This is a simplified version that demonstrates the TUI functionality.
"""

import logging
import os
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from openhands_cli.argparsers.main_parser import create_main_parser
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.utils import create_seeded_instructions_from_args


console = Console()


env_path = Path.cwd() / ".env"
if env_path.is_file():
    load_dotenv(dotenv_path=str(env_path), override=False)


debug_env = os.getenv("DEBUG", "false").lower()
if debug_env != "1" and debug_env != "true":
    logging.disable(logging.WARNING)
    warnings.filterwarnings("ignore")


def handle_resume_logic(args) -> str | None:
    """Handle resume logic and return the conversation ID to resume.

    Args:
        args: Parsed command line arguments

    Returns:
        Conversation ID to resume, or None if should show conversation list or exit
    """
    # Check if --last flag is used
    if args.last:
        if args.resume is None:
            console.print(
                "Error: --last flag requires --resume", style=OPENHANDS_THEME.warning
            )
            return None

        # Get the latest conversation ID
        from openhands_cli.conversations.lister import ConversationLister

        lister = ConversationLister()
        latest_id = lister.get_latest_conversation_id()

        if latest_id is None:
            console.print(
                "No conversations found to resume.", style=OPENHANDS_THEME.warning
            )
            return None

        console.print(
            f"Resuming latest conversation: {latest_id}",
            style=OPENHANDS_THEME.success,
        )
        return latest_id

    # Check if resume was called without ID and without --last
    elif args.resume is not None and args.resume == "":
        # Resume called without ID - show conversation list
        from openhands_cli.conversations.display import display_recent_conversations

        display_recent_conversations()
        return None

    # Return the resume ID as-is (could be None for new conversation)
    return args.resume


def main() -> None:
    """Main entry point for the OpenHands CLI.

    Raises:
        ImportError: If agent chat dependencies are missing
        Exception: On other error conditions
    """
    parser = create_main_parser()
    args = parser.parse_args()

    # Handle --json flag (only works with --headless)
    json_mode = args.json and args.headless

    # Validate headless mode requirements
    if args.headless and not args.task and not args.file:
        parser.error("--headless requires either --task or --file to be specified")

    # Automatically set exit_without_confirmation when headless mode is used
    if args.headless:
        args.exit_without_confirmation = True

    try:
        if args.command == "serve":
            # Import gui_launcher only when needed
            from openhands_cli.gui_launcher import launch_gui_server

            launch_gui_server(mount_cwd=args.mount_cwd, gpu=args.gpu)
        elif args.command == "web":
            # Import web server launcher only when needed
            from openhands_cli.serve import launch_web_server

            launch_web_server(host=args.host, port=args.port, debug=args.debug)
        elif args.command == "acp":
            import asyncio

            from openhands_cli.acp_impl.agent import run_acp_server
            from openhands_cli.acp_impl.confirmation import ConfirmationMode

            # Determine confirmation mode from arguments
            confirmation_mode: ConfirmationMode = "always-ask"  # default
            if args.always_approve:
                confirmation_mode = "always-approve"
            elif args.llm_approve:
                confirmation_mode = "llm-approve"

            asyncio.run(run_acp_server(initial_confirmation_mode=confirmation_mode))

        elif args.command == "login":
            from openhands_cli.auth.login_command import run_login_command

            success = run_login_command(args.server_url)
            if not success:
                sys.exit(1)
        elif args.command == "logout":
            from openhands_cli.auth.logout_command import run_logout_command

            success = run_logout_command(args.server_url)
            if not success:
                sys.exit(1)
        elif args.command == "mcp":
            # Import MCP command handler only when needed
            from openhands_cli.mcp.mcp_commands import handle_mcp_command

            handle_mcp_command(args)
        elif args.command == "cloud":
            # Validate cloud mode requirements
            if not args.task and not args.file:
                parser.error(
                    "cloud subcommand requires either --task or --file to be specified"
                )

            from openhands_cli.cloud.command import handle_cloud_command

            handle_cloud_command(args)

        else:
            # Handle resume logic (including --last and conversation list)
            resume_id = handle_resume_logic(args)
            if resume_id is None and (args.last or args.resume == ""):
                # Either showed conversation list or had an error
                return

            # Use textual-based UI as default (experimental UI is now the default)
            # The --exp flag is kept for compatibility but does the same thing
            from openhands_cli.refactor.textual_app import main as textual_main

            queued_inputs = create_seeded_instructions_from_args(args)
            conversation_id = textual_main(
                resume_conversation_id=resume_id,
                queued_inputs=queued_inputs,
                always_approve=args.always_approve,
                llm_approve=args.llm_approve,
                exit_without_confirmation=args.exit_without_confirmation,
                headless=args.headless,
                json_mode=json_mode,
            )
            console.print("Goodbye! 👋", style=OPENHANDS_THEME.success)
            console.print(
                f"Conversation ID: {conversation_id.hex}",
                style=OPENHANDS_THEME.accent,
            )
            console.print(
                f"Hint: run openhands --resume {conversation_id} "
                "to resume this conversation.",
                style=OPENHANDS_THEME.secondary,
            )
    except KeyboardInterrupt:
        console.print("\nGoodbye! 👋", style=OPENHANDS_THEME.warning)
    except EOFError:
        console.print("\nGoodbye! 👋", style=OPENHANDS_THEME.warning)
    except Exception as e:
        console.print(f"Error: {str(e)}", style=OPENHANDS_THEME.error, markup=False)
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
