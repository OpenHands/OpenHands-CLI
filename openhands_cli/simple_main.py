#!/usr/bin/env python3
"""
Simple main entry point for OpenHands CLI.
This is a simplified version that demonstrates the TUI functionality.
"""

import logging
import os
import warnings

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.argparsers.main_parser import create_main_parser
from openhands_cli.utils import create_seeded_instructions_from_args


debug_env = os.getenv("DEBUG", "false").lower()
if debug_env != "1" and debug_env != "true":
    logging.disable(logging.WARNING)
    warnings.filterwarnings("ignore")


def main() -> None:
    """Main entry point for the OpenHands CLI.

    Raises:
        ImportError: If agent chat dependencies are missing
        Exception: On other error conditions
    """
    parser = create_main_parser()
    args = parser.parse_args()

    try:
        if args.command == "serve":
            # Import gui_launcher only when needed
            from openhands_cli.gui_launcher import launch_gui_server

            launch_gui_server(mount_cwd=args.mount_cwd, gpu=args.gpu)
        elif args.command == "acp":
            import asyncio

            from openhands_cli.acp_impl.agent import run_acp_server

            asyncio.run(run_acp_server())
        else:
            # Default CLI behavior - no subcommand needed
            # Import agent_chat only when needed
            from openhands_cli.agent_chat import run_cli_entry

            queued_inputs = create_seeded_instructions_from_args(args)

            # Start agent chat
            run_cli_entry(
                resume_conversation_id=args.resume,
                queued_inputs=queued_inputs,
            )
    except KeyboardInterrupt:
        print_formatted_text(HTML("\n<yellow>Goodbye! 👋</yellow>"))
    except EOFError:
        print_formatted_text(HTML("\n<yellow>Goodbye! 👋</yellow>"))
    except Exception as e:
        print_formatted_text(HTML(f"<red>Error: {e}</red>"))
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
