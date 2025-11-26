"""OpenHands Agent Client Protocol (ACP) server implementation."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from acp import (
    Agent as ACPAgent,
    AgentSideConnection,
    InitializeRequest,
    InitializeResponse,
    NewSessionRequest,
    NewSessionResponse,
    PromptRequest,
    PromptResponse,
    RequestError,
    SessionNotification,
    stdio_streams,
)
from acp.schema import (
    AgentCapabilities,
    AgentMessageChunk,
    AuthenticateRequest,
    AuthenticateResponse,
    CancelNotification,
    Implementation,
    LoadSessionRequest,
    LoadSessionResponse,
    McpCapabilities,
    PromptCapabilities,
    SetSessionModelRequest,
    SetSessionModelResponse,
    SetSessionModeRequest,
    SetSessionModeResponse,
    TextContentBlock,
)

from openhands.sdk import (
    BaseConversation,
    Conversation,
    Message,
    Workspace,
)
from openhands.sdk.event import Event
from openhands_cli import __version__
from openhands_cli.acp_impl.event import EventSubscriber
from openhands_cli.acp_impl.utils import (
    RESOURCE_SKILL,
    convert_acp_mcp_servers_to_agent_format,
    convert_acp_prompt_to_message_content,
)
from openhands_cli.locations import CONVERSATIONS_DIR, WORK_DIR
from openhands_cli.setup import MissingAgentSpec, load_agent_specs


logger = logging.getLogger(__name__)


class OpenHandsACPAgent(ACPAgent):
    """OpenHands Agent Client Protocol implementation."""

    def __init__(self, conn: AgentSideConnection):
        """Initialize the OpenHands ACP agent.

        Args:
            conn: ACP connection for sending notifications
        """
        self._conn = conn
        # Cache of active conversations to preserve state (pause, confirmation, etc.)
        # across multiple operations on the same session
        self._active_sessions: dict[str, BaseConversation] = {}
        # Track running tasks for each session to ensure proper cleanup on cancel
        self._running_tasks: dict[str, asyncio.Task] = {}

        logger.info("OpenHands ACP Agent initialized")

    def _get_or_create_conversation(
        self,
        session_id: str,
        working_dir: str | None = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> BaseConversation:
        """Get an active conversation from cache or create/load it.

        This maintains conversation state (pause, confirmation, etc.) across
        multiple operations on the same session.

        Args:
            session_id: Session/conversation ID (UUID string)
            working_dir: Working directory for workspace (only for new sessions)
            mcp_servers: MCP servers config (only for new sessions)

        Returns:
            Cached or newly created/loaded conversation
        """
        # Check if we already have this conversation active
        if session_id in self._active_sessions:
            logger.debug(f"Using cached conversation for session {session_id}")
            return self._active_sessions[session_id]

        # Create/load new conversation
        logger.debug(f"Creating new conversation for session {session_id}")
        conversation = self._setup_acp_conversation(
            session_id=session_id,
            working_dir=working_dir,
            mcp_servers=mcp_servers,
        )

        # Cache it for future operations
        self._active_sessions[session_id] = conversation
        return conversation

    def _setup_acp_conversation(
        self,
        session_id: str,
        working_dir: str | None = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> BaseConversation:
        """Set up a conversation for ACP with event streaming support.

        This function reuses the resume logic from
        openhands_cli.setup.setup_conversation but adapts it for ACP by using
        EventSubscriber instead of CLIVisualizer.

        The SDK's Conversation class automatically:
        - Loads from disk if conversation_id exists in persistence_dir
        - Creates a new conversation if it doesn't exist

        Args:
            session_id: Session/conversation ID (UUID string)
            working_dir: Working directory for the workspace. Defaults to WORK_DIR.
            mcp_servers: Optional MCP servers configuration

        Returns:
            Configured conversation that's either loaded from disk or newly created

        Raises:
            MissingAgentSpec: If agent configuration is missing
        """
        # Load agent specs (same as setup_conversation)
        agent = load_agent_specs(
            conversation_id=session_id,
            mcp_servers=mcp_servers,
            skills=[RESOURCE_SKILL],
        )

        # Validate and setup workspace
        if working_dir is None:
            working_dir = WORK_DIR
        working_path = Path(working_dir)

        if not working_path.exists():
            logger.warning(
                f"Working directory {working_dir} doesn't exist, creating it"
            )
            working_path.mkdir(parents=True, exist_ok=True)

        if not working_path.is_dir():
            raise RequestError.invalid_params(
                {"reason": f"Working directory path is not a directory: {working_dir}"}
            )

        workspace = Workspace(working_dir=str(working_path))

        # Create event subscriber for streaming updates (ACP-specific)
        subscriber = EventSubscriber(session_id, self._conn)

        # Get the current event loop for the callback
        loop = asyncio.get_event_loop()

        def sync_callback(event: Event) -> None:
            """Synchronous wrapper that schedules async event handling."""
            asyncio.run_coroutine_threadsafe(subscriber(event), loop)

        # Create conversation with persistence support
        # The SDK automatically loads from disk if conversation_id exists
        conversation = Conversation(
            agent=agent,
            workspace=workspace,
            persistence_dir=CONVERSATIONS_DIR,
            conversation_id=UUID(session_id),
            callbacks=[sync_callback],
            visualizer=None,  # No visualizer needed for ACP
        )

        # # Set up security analyzer (same as setup_conversation with confirmation mode)
        # conversation.set_security_analyzer(LLMSecurityAnalyzer())
        # conversation.set_confirmation_policy(AlwaysConfirm())
        # TODO: implement later

        return conversation

    async def initialize(self, params: InitializeRequest) -> InitializeResponse:
        """Initialize the ACP protocol."""
        logger.info(f"Initializing ACP with protocol version: {params.protocolVersion}")

        # Check if agent is configured
        try:
            load_agent_specs()
            auth_methods = []
            logger.info("Agent configured, no authentication required")
        except MissingAgentSpec:
            # Agent not configured - this shouldn't happen in production
            # but we'll return empty auth methods for now
            auth_methods = []
            logger.warning("Agent not configured - users should run 'openhands' first")

        return InitializeResponse(
            protocolVersion=params.protocolVersion,
            authMethods=auth_methods,
            agentCapabilities=AgentCapabilities(
                loadSession=True,
                mcpCapabilities=McpCapabilities(http=True, sse=True),
                promptCapabilities=PromptCapabilities(
                    audio=False,
                    embeddedContext=True,
                    image=True,
                ),
            ),
            agentInfo=Implementation(
                name="OpenHands CLI ACP Agent",
                version=__version__,
            ),
        )

    async def authenticate(
        self, params: AuthenticateRequest
    ) -> AuthenticateResponse | None:
        """Authenticate the client (no-op for now)."""
        logger.info(f"Authentication requested with method: {params.methodId}")
        return AuthenticateResponse()

    async def newSession(self, params: NewSessionRequest) -> NewSessionResponse:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())

        try:
            # Convert ACP MCP servers to Agent format
            mcp_servers_dict = None
            if params.mcpServers:
                mcp_servers_dict = convert_acp_mcp_servers_to_agent_format(
                    params.mcpServers
                )

            # Validate working directory
            working_dir = params.cwd or str(Path.cwd())
            logger.info(f"Using working directory: {working_dir}")

            # Create conversation and cache it for future operations
            # This reuses the same pattern as openhands --resume
            conversation = self._get_or_create_conversation(
                session_id=session_id,
                working_dir=working_dir,
                mcp_servers=mcp_servers_dict,
            )

            logger.info(
                f"Created new session {session_id} with model: "
                f"{conversation.agent.llm.model}"  # type: ignore[attr-defined]
            )

            return NewSessionResponse(sessionId=session_id)

        except MissingAgentSpec as e:
            logger.error(f"Agent not configured: {e}")
            raise RequestError.internal_error(
                {
                    "reason": "Agent not configured",
                    "details": "Please run 'openhands' to configure the agent first.",
                }
            )
        except RequestError:
            # Re-raise RequestError as-is
            raise
        except Exception as e:
            logger.error(f"Failed to create new session: {e}", exc_info=True)
            raise RequestError.internal_error(
                {"reason": "Failed to create new session", "details": str(e)}
            )

    async def prompt(self, params: PromptRequest) -> PromptResponse:
        """Handle a prompt request."""
        session_id = params.sessionId

        try:
            # Get or create conversation (preserves state like pause/confirmation)
            conversation = self._get_or_create_conversation(session_id=session_id)

            # Convert ACP prompt format to OpenHands message content
            message_content = convert_acp_prompt_to_message_content(params.prompt)

            if not message_content:
                return PromptResponse(stopReason="end_turn")

            # Send the message with potentially multiple content types
            # (text + images)
            message = Message(role="user", content=message_content)
            conversation.send_message(message)

            # Run the conversation asynchronously
            # Callbacks are already set up when conversation was created
            # Track the running task so cancel() can wait for proper cleanup
            run_task = asyncio.create_task(asyncio.to_thread(conversation.run))
            self._running_tasks[session_id] = run_task
            try:
                await run_task
            finally:
                # Clean up task tracking
                self._running_tasks.pop(session_id, None)

            # Return the final response
            return PromptResponse(stopReason="end_turn")

        except RequestError:
            # Re-raise RequestError as-is
            raise
        except Exception as e:
            logger.error(f"Error processing prompt: {e}", exc_info=True)
            # Send error notification to client
            await self._conn.sessionUpdate(
                SessionNotification(
                    sessionId=session_id,
                    update=AgentMessageChunk(
                        sessionUpdate="agent_message_chunk",
                        content=TextContentBlock(type="text", text=f"Error: {str(e)}"),
                    ),
                )
            )
            raise RequestError.internal_error(
                {"reason": "Failed to process prompt", "details": str(e)}
            )

    async def _wait_for_task_completion(
        self, task: asyncio.Task, session_id: str, timeout: float = 10.0
    ) -> None:
        """Wait for a task to complete and handle cancellation if needed."""
        try:
            await asyncio.wait_for(task, timeout=timeout)
        except TimeoutError:
            logger.warning(
                f"Conversation thread did not stop within timeout for session "
                f"{session_id}"
            )
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        except Exception as e:
            logger.error(f"Error while waiting for conversation to stop: {e}")
            raise RequestError.internal_error(
                {
                    "reason": "Error during conversation cancellation",
                    "details": str(e),
                }
            )

    async def cancel(self, params: CancelNotification) -> None:
        """Cancel the current operation."""
        logger.info(f"Cancel requested for session: {params.sessionId}")

        try:
            conversation = self._get_or_create_conversation(session_id=params.sessionId)
            conversation.pause()

            running_task = self._running_tasks.get(params.sessionId)
            if not running_task or running_task.done():
                return

            logger.debug(
                f"Waiting for conversation thread to terminate for session "
                f"{params.sessionId}"
            )
            await self._wait_for_task_completion(running_task, params.sessionId)

        except RequestError:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel session {params.sessionId}: {e}")
            raise RequestError.internal_error(
                {"reason": "Failed to cancel session", "details": str(e)}
            )

    async def loadSession(
        self, params: LoadSessionRequest
    ) -> LoadSessionResponse | None:
        """Load an existing session and replay conversation history.

        This implements the same logic as 'openhands --resume <session_id>':
        - Uses _setup_acp_conversation which calls the SDK's Conversation constructor
        - The SDK automatically loads from persistence_dir if conversation_id exists
        - Streams the loaded history back to the client

        Per ACP spec (https://agentclientprotocol.com/protocol/session-setup#loading-sessions):
        - Server should load the session state from persistent storage
        - Replay the conversation history to the client via sessionUpdate notifications
        """
        session_id = params.sessionId
        logger.info(f"Loading session: {session_id}")

        try:
            # Validate session ID format
            try:
                UUID(session_id)
            except ValueError:
                raise RequestError.invalid_params(
                    {"reason": "Invalid session ID format", "sessionId": session_id}
                )

            # Get or create conversation (loads from disk if not in cache)
            # The SDK's Conversation class automatically loads from disk if the
            # conversation_id exists in persistence_dir
            conversation = self._get_or_create_conversation(session_id=session_id)

            # Check if there's actually any history to load
            if not conversation.state.events:
                logger.warning(
                    f"Session {session_id} has no history (new or empty session)"
                )
                return LoadSessionResponse()

            # Stream conversation history to client by reusing EventSubscriber
            # This ensures consistent event handling with live conversations
            logger.info(
                f"Streaming {len(conversation.state.events)} events from "
                f"conversation history"
            )
            subscriber = EventSubscriber(session_id, self._conn)
            for event in conversation.state.events:
                await subscriber(event)

            logger.info(f"Successfully loaded session {session_id}")
            return LoadSessionResponse()

        except RequestError:
            # Re-raise RequestError as-is
            raise
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}", exc_info=True)
            raise RequestError.internal_error(
                {"reason": "Failed to load session", "details": str(e)}
            )

    async def setSessionMode(
        self, params: SetSessionModeRequest
    ) -> SetSessionModeResponse | None:
        """Set session mode (no-op for now)."""
        logger.info(f"Set session mode requested: {params.sessionId}")
        return SetSessionModeResponse()

    async def setSessionModel(
        self, params: SetSessionModelRequest
    ) -> SetSessionModelResponse | None:
        """Set session model (no-op for now)."""
        logger.info(f"Set session model requested: {params.sessionId}")
        return SetSessionModelResponse()

    async def extMethod(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Extension method (not supported)."""
        logger.info(f"Extension method '{method}' requested with params: {params}")
        return {"error": "extMethod not supported"}

    async def extNotification(self, method: str, params: dict[str, Any]) -> None:
        """Extension notification (no-op for now)."""
        logger.info(f"Extension notification '{method}' received with params: {params}")


async def run_acp_server() -> None:
    """Run the OpenHands ACP server."""
    logger.info("Starting OpenHands ACP server...")

    reader, writer = await stdio_streams()

    def create_agent(conn: AgentSideConnection) -> OpenHandsACPAgent:
        return OpenHandsACPAgent(conn)

    AgentSideConnection(create_agent, writer, reader)

    # Keep the server running
    await asyncio.Event().wait()
