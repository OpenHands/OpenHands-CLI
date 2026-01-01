"""OpenHands Cloud ACP Server runner.

This module provides the entry point for running the ACP server with
OpenHands Cloud workspace support.
"""

import asyncio
import logging
import sys

from acp import Client, stdio_streams
from acp.core import AgentSideConnection
from rich.console import Console

from openhands_cli.acp_impl.agent import OpenHandsCloudACPAgent
from openhands_cli.acp_impl.confirmation import ConfirmationMode
from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.cloud.conversation import is_token_valid
from openhands_cli.theme import OPENHANDS_THEME


logger = logging.getLogger(__name__)
console = Console()


class CloudAuthenticationError(Exception):
    """Exception raised for cloud authentication errors."""


def _print_login_instructions(msg: str) -> None:
    """Print login instructions to the user."""
    console.print(f"[{OPENHANDS_THEME.error}]{msg}[/{OPENHANDS_THEME.error}]")
    console.print(
        f"[{OPENHANDS_THEME.secondary}]"
        "Please run the following command to authenticate:"
        f"[/{OPENHANDS_THEME.secondary}]"
    )
    console.print(
        f"[{OPENHANDS_THEME.accent}]  openhands login[/{OPENHANDS_THEME.accent}]"
    )


def _logout_and_instruct(server_url: str) -> None:
    """Log out and instruct the user to re-authenticate."""
    from openhands_cli.auth.logout_command import logout_command

    console.print(
        f"[{OPENHANDS_THEME.warning}]Your connection with OpenHands Cloud has expired."
        f"[/{OPENHANDS_THEME.warning}]"
    )
    console.print(
        f"[{OPENHANDS_THEME.accent}]Logging you out...[/{OPENHANDS_THEME.accent}]"
    )
    logout_command(server_url)
    console.print(
        f"[{OPENHANDS_THEME.secondary}]"
        "Please re-run the following command to reconnect and retry:"
        f"[/{OPENHANDS_THEME.secondary}]"
    )
    console.print(
        f"[{OPENHANDS_THEME.accent}]  openhands login[/{OPENHANDS_THEME.accent}]"
    )


def require_api_key() -> str:
    """Return stored API key or raise with a helpful message.

    Returns:
        The stored API key

    Raises:
        CloudAuthenticationError: If the user is not authenticated
    """
    store = TokenStorage()

    if not store.has_api_key():
        _print_login_instructions("Error: You are not logged in to OpenHands Cloud.")
        raise CloudAuthenticationError("User not authenticated")

    api_key = store.get_api_key()
    if not api_key:
        _print_login_instructions("Error: Invalid API key stored.")
        raise CloudAuthenticationError("Invalid API key")

    return api_key


async def validate_cloud_credentials(
    cloud_api_url: str,
) -> str:
    """Validate cloud credentials before starting the ACP server.

    Args:
        cloud_api_url: The OpenHands Cloud API URL

    Returns:
        The validated API key

    Raises:
        CloudAuthenticationError: If authentication fails
    """
    # Get the API key from storage
    api_key = require_api_key()

    # Validate the token with the cloud API
    console.print(
        f"[{OPENHANDS_THEME.secondary}]Validating OpenHands Cloud credentials..."
        f"[/{OPENHANDS_THEME.secondary}]",
    )

    try:
        if not await is_token_valid(cloud_api_url, api_key):
            _logout_and_instruct(cloud_api_url)
            raise CloudAuthenticationError("Authentication expired - user logged out")
    except CloudAuthenticationError:
        raise
    except Exception as e:
        console.print(
            f"[{OPENHANDS_THEME.error}]Failed to validate credentials: {e}"
            f"[/{OPENHANDS_THEME.error}]",
        )
        raise CloudAuthenticationError(f"Failed to validate credentials: {e}") from e

    console.print(
        f"[{OPENHANDS_THEME.success}]✓ OpenHands Cloud credentials validated"
        f"[/{OPENHANDS_THEME.success}]",
    )

    return api_key


async def run_cloud_acp_server(
    initial_confirmation_mode: ConfirmationMode = "always-ask",
    resume_conversation_id: str | None = None,
    streaming_enabled: bool = False,
    cloud_api_url: str = "https://app.all-hands.dev",
) -> None:
    """Run the OpenHands Cloud ACP server.

    This function validates the cloud credentials before starting the server,
    ensuring the user is authenticated with OpenHands Cloud.

    Args:
        initial_confirmation_mode: Default confirmation mode for new sessions
        resume_conversation_id: Optional conversation ID to resume when a new
            session is created
        streaming_enabled: Whether to enable token streaming for LLM outputs
        cloud_api_url: The OpenHands Cloud API URL
    """
    logger.info(
        f"Starting OpenHands Cloud ACP server with confirmation mode: "
        f"{initial_confirmation_mode}, streaming: {streaming_enabled}..."
    )
    if resume_conversation_id:
        logger.info(f"Will resume conversation: {resume_conversation_id}")

    # Validate credentials before starting the server
    try:
        api_key = await validate_cloud_credentials(cloud_api_url)
    except CloudAuthenticationError:
        # Error messages already printed
        sys.exit(1)

    console.print(
        f"[{OPENHANDS_THEME.accent}]Starting OpenHands Cloud ACP server..."
        f"[/{OPENHANDS_THEME.accent}]",
    )

    reader, writer = await stdio_streams()

    def create_agent(conn: Client) -> OpenHandsCloudACPAgent:
        return OpenHandsCloudACPAgent(
            conn=conn,
            cloud_api_key=api_key,
            cloud_api_url=cloud_api_url,
        )

    AgentSideConnection(create_agent, writer, reader)

    # Keep the server running
    await asyncio.Event().wait()
