"""Cloud command handler for OpenHands CLI."""

import argparse
import asyncio
import sys

from openhands_cli.auth.utils import (
    AuthenticationError,
    console_print,
    ensure_valid_auth,
)
from openhands_cli.cloud.conversation import (
    CloudConversationError,
    create_cloud_conversation,
)
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.utils import create_seeded_instructions_from_args


async def _run_cloud_conversation(server_url: str, initial_message: str) -> None:
    """Run cloud conversation with authentication."""
    api_key = await ensure_valid_auth(server_url)
    await create_cloud_conversation(
        server_url=server_url,
        api_key=api_key,
        initial_user_msg=initial_message,
    )


def handle_cloud_command(args: argparse.Namespace) -> None:
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
            console_print(
                "Error: No initial message provided for cloud conversation.",
                style=OPENHANDS_THEME.error,
            )
            console_print(
                "Use --task or --file to provide an initial message.",
                style=OPENHANDS_THEME.secondary,
            )
            return

        initial_message = queued_inputs[0]

        # Ensure authentication and create cloud conversation
        asyncio.run(_run_cloud_conversation(args.server_url, initial_message))

        console_print(
            "Cloud conversation created successfully! 🚀",
            style=OPENHANDS_THEME.success,
        )

    except (CloudConversationError, AuthenticationError):
        # Error already printed in the function
        sys.exit(1)
    except Exception as e:
        console_print(f"Unexpected error: {e}", style=OPENHANDS_THEME.error)
        sys.exit(1)
