import asyncio
import logging
import sys

from acp import Client, stdio_streams
from acp.core import AgentSideConnection
from acp.schema import (
    SessionModeState,
)

from openhands_cli.acp_impl.agent.remote_agent import (
    OpenHandsCloudACPAgent,
    validate_cloud_credentials,
)
from openhands_cli.acp_impl.confirmation import (
    ConfirmationMode,
    get_available_modes,
)


logger = logging.getLogger(__name__)


def get_session_mode_state(current_mode: ConfirmationMode) -> SessionModeState:
    """Get the session mode state for a given confirmation mode.

    Args:
        current_mode: The current confirmation mode

    Returns:
        SessionModeState with available modes and current mode
    """
    return SessionModeState(
        current_mode_id=current_mode,
        available_modes=get_available_modes(),
    )


async def run_acp_server(
    initial_confirmation_mode: ConfirmationMode = "always-ask",
    resume_conversation_id: str | None = None,
    streaming_enabled: bool = False,
    cloud: bool = False,
    cloud_api_url: str = "https://app.all-hands.dev",
) -> None:
    """Run the OpenHands ACP server.

    Args:
        initial_confirmation_mode: Default confirmation mode for new sessions
        resume_conversation_id: Optional conversation ID to resume when a new
            session is created
        streaming_enabled: Whether to enable token streaming for LLM outputs
    """
    logger.info(
        f"Starting OpenHands ACP server with confirmation mode: "
        f"{initial_confirmation_mode}, streaming: {streaming_enabled}..."
    )
    if resume_conversation_id:
        logger.info(f"Will resume conversation: {resume_conversation_id}")

    reader, writer = await stdio_streams()

    if not cloud:
        from openhands_cli.acp_impl.agent.local_agent import LocalOpenHandsACPAgent

        def create_local_agent(conn: Client) -> LocalOpenHandsACPAgent:
            return LocalOpenHandsACPAgent(
                conn,
                initial_confirmation_mode,
                resume_conversation_id,
                streaming_enabled,
            )

        AgentSideConnection(create_local_agent, writer, reader)

    else:
        try:
            api_key = await validate_cloud_credentials(cloud_api_url)
        except Exception:
            # Error messages already printed
            sys.exit(1)

        def create_agent(conn: Client) -> OpenHandsCloudACPAgent:
            return OpenHandsCloudACPAgent(
                conn=conn,
                cloud_api_key=api_key,
                cloud_api_url=cloud_api_url,
            )

        AgentSideConnection(create_agent, writer, reader)

    # Keep the server running
    await asyncio.Event().wait()
