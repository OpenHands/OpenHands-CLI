"""Cloud command handler for OpenHands CLI."""

import asyncio
import sys

from rich.console import Console

from openhands_cli.cloud.conversation import (
    CloudConversationError,
    create_cloud_conversation,
)
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.utils import create_seeded_instructions_from_args


console = Console()


def handle_cloud_command(args) -> None:
    """Handle cloud command execution.

    Args:
        args: Parsed command line arguments

    Raises:
        SystemExit: On error conditions
    """
    try:
        # Get the initial message from args
        queued_inputs = create_seeded_instructions_from_args(args)
        if not queued_inputs:
            console.print(
                f"[{OPENHANDS_THEME.error}]Error: No initial message "
                f"provided for cloud conversation."
                f"[/{OPENHANDS_THEME.error}]"
            )
            console.print(
                f"[{OPENHANDS_THEME.secondary}]Use --task or --file to "
                f"provide an initial message.[/{OPENHANDS_THEME.secondary}]"
            )
            return

        initial_message = queued_inputs[0]

        # Create cloud conversation
        asyncio.run(
            create_cloud_conversation(
                server_url=args.server_url,
                initial_user_msg=initial_message,
            )
        )

        console.print(
            f"[{OPENHANDS_THEME.success}]Cloud conversation created "
            f"successfully! 🚀[/{OPENHANDS_THEME.success}]"
        )

    except CloudConversationError:
        # Error already printed in the function
        sys.exit(1)
    except Exception as e:
        console.print(
            f"[{OPENHANDS_THEME.error}]Unexpected error: "
            f"{str(e)}[/{OPENHANDS_THEME.error}]"
        )
        sys.exit(1)
