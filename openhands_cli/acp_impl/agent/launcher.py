import asyncio
import logging

from acp import Client, stdio_streams
from acp.core import AgentSideConnection

from openhands_cli.acp_impl.agent.remote_agent import (
    OpenHandsCloudACPAgent,
)
from openhands_cli.acp_impl.confirmation import ConfirmationMode
from openhands_cli.acp_impl.debug_logger import DebugLogger


logger = logging.getLogger(__name__)


async def run_acp_server(
    initial_confirmation_mode: ConfirmationMode = "always-ask",
    resume_conversation_id: str | None = None,
    streaming_enabled: bool = False,
    cloud: bool = False,
    cloud_api_url: str = "https://app.all-hands.dev",
    debug: bool = False,
) -> None:
    """Run the OpenHands ACP server.

    Args:
        initial_confirmation_mode: Default confirmation mode for new sessions
        resume_conversation_id: Optional conversation ID to resume when a new
            session is created
        streaming_enabled: Whether to enable token streaming for LLM outputs
        cloud: Whether to use OpenHands Cloud instead of local workspace
        cloud_api_url: OpenHands Cloud API URL
        debug: Whether to enable debug logging of all ACP protocol messages
    """
    logger.info(
        f"Starting OpenHands ACP server with confirmation mode: "
        f"{initial_confirmation_mode}, streaming: {streaming_enabled}..."
    )
    if resume_conversation_id:
        logger.info(f"Will resume conversation: {resume_conversation_id}")

    # Setup debug observer if enabled
    debug_logger = DebugLogger() if debug else None
    observers = [debug_logger] if debug_logger else None
    if debug_logger:
        logger.info(f"Debug logging enabled: {debug_logger.log_file}")

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

        AgentSideConnection(create_local_agent, writer, reader, observers=observers)

    else:

        def create_agent(conn: Client) -> OpenHandsCloudACPAgent:
            return OpenHandsCloudACPAgent(
                conn=conn,
                initial_confirmation_mode=initial_confirmation_mode,
                cloud_api_url=cloud_api_url,
                resume_conversation_id=resume_conversation_id,
            )

        AgentSideConnection(create_agent, writer, reader, observers=observers)

    # Keep the server running
    await asyncio.Event().wait()
