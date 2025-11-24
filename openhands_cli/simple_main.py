#!/usr/bin/env python3
"""
Simple main entry point for OpenHands CLI.
This is a simplified version that demonstrates the TUI functionality.
"""

import logging
import os
from pathlib import Path
import warnings

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.argparsers.main_parser import create_main_parser


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

    initial_message: str | None = None
    if args.command != "serve":
        # --file takes precedence over --task
        if getattr(args, "file", None):
            path = Path(args.file).expanduser()
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                print_formatted_text(
                    HTML(f"<red>Failed to read file {path}: {exc}</red>")
                )
                raise SystemExit(1)

            initial_message = (
                "Starting this session with file context.\n\n"
                f"File path: {path}\n\n"
                "File contents:\n"
                "--------------------\n"
                f"{content}\n"
                "--------------------\n"
            )
        elif getattr(args, "task", None):
            initial_message = args.task

    try:
        if args.command == "serve":
            # Import gui_launcher only when needed
            from openhands_cli.gui_launcher import launch_gui_server

            launch_gui_server(mount_cwd=args.mount_cwd, gpu=args.gpu)
        else:
            # Default CLI behavior - no subcommand needed
            # Import agent_chat only when needed
            from openhands_cli.agent_chat import run_cli_entry

            # Start agent chat
            run_cli_entry(
                resume_conversation_id=args.resume,
                initial_message=initial_message,
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
