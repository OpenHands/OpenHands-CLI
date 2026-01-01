"""OpenHands Cloud ACP Agent implementation.

This module provides the ACP agent implementation that uses OpenHands Cloud
for sandbox environments instead of local workspace.
"""

import asyncio
import logging
import uuid
from typing import Any, cast
from uuid import UUID

from acp import (
    Agent as ACPAgent,
    Client,
    InitializeResponse,
    NewSessionResponse,
    PromptResponse,
    RequestError,
)
from acp.helpers import update_current_mode
from acp.schema import (
    AgentCapabilities,
    AgentMessageChunk,
    AuthenticateResponse,
    Implementation,
    ListSessionsResponse,
    LoadSessionResponse,
    McpCapabilities,
    PromptCapabilities,
    SetSessionModelResponse,
    SetSessionModeResponse,
    TextContentBlock,
)

from openhands.sdk import (
    Conversation,
    Event,
    Message,
    RemoteConversation,
)
from openhands.workspace import OpenHandsCloudWorkspace
from openhands_cli import __version__
from openhands_cli.acp_impl.agent.util import get_session_mode_state
from openhands_cli.acp_impl.confirmation import (
    ConfirmationMode,
)
from openhands_cli.acp_impl.events.event import EventSubscriber
from openhands_cli.acp_impl.slash_commands import (
    VALID_CONFIRMATION_MODE,
    apply_confirmation_mode_to_conversation,
    get_confirmation_mode_from_conversation,
    validate_confirmation_mode,
)
from openhands_cli.acp_impl.utils import (
    RESOURCE_SKILL,
    convert_acp_mcp_servers_to_agent_format,
    convert_acp_prompt_to_message_content,
)
from openhands_cli.locations import MCP_CONFIG_FILE
from openhands_cli.mcp.mcp_utils import MCPConfigurationError
from openhands_cli.setup import MissingAgentSpec, load_agent_specs


logger = logging.getLogger(__name__)


class OpenHandsCloudACPAgent(ACPAgent):
    """OpenHands Cloud ACP Agent that uses OpenHands Cloud for sandbox environments.

    This agent connects to OpenHands Cloud (app.all-hands.dev) to provision
    sandboxed environments for agent execution instead of using local workspace.
    """

    def __init__(
        self,
        conn: Client,
        cloud_api_key: str,
        cloud_api_url: str = "https://app.all-hands.dev",
        resume_conversation_id: str | None = None,
    ):
        """Initialize the OpenHands Cloud ACP agent.

        Args:
            conn: ACP connection for sending notifications
            initial_confirmation_mode: Default confirmation mode for new sessions
            cloud_api_key: API key for OpenHands Cloud authentication
            cloud_api_url: OpenHands Cloud API URL
            resume_conversation_id: Optional conversation ID to resume
            streaming_enabled: Whether to enable token streaming for LLM outputs
        """
        self._conn = conn
        # Track running tasks for each session to ensure proper cleanup on cancel
        self._running_tasks: dict[str, asyncio.Task] = {}
        # Conversation ID to resume (from --resume flag)
        self._resume_conversation_id: str | None = resume_conversation_id
        if resume_conversation_id:
            logger.info(f"Will resume conversation: {resume_conversation_id}")

        self._cloud_api_key = cloud_api_key
        self._cloud_api_url = cloud_api_url

        # Track active cloud workspaces for cleanup
        self._active_sessions: dict[str, RemoteConversation] = {}
        self._active_workspaces: dict[str, OpenHandsCloudWorkspace] = {}

        logger.info(
            f"OpenHands Cloud ACP Agent initialized with cloud URL: {cloud_api_url}"
        )

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: Any | None = None,  # noqa: ARG002
        client_info: Any | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> InitializeResponse:
        """Initialize the ACP protocol."""
        logger.info(f"Initializing ACP with protocol version: {protocol_version}")

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
            protocol_version=protocol_version,
            auth_methods=auth_methods,
            agent_capabilities=AgentCapabilities(
                load_session=True,
                mcp_capabilities=McpCapabilities(http=True, sse=True),
                prompt_capabilities=PromptCapabilities(
                    audio=False,
                    embedded_context=True,
                    image=True,
                ),
            ),
            agent_info=Implementation(
                name="OpenHands CLI ACP Agent",
                version=__version__,
            ),
        )

    async def set_session_mode(
        self,
        mode_id: str,
        session_id: str,
        **_kwargs: Any,
    ) -> SetSessionModeResponse | None:
        """Set session mode by updating confirmation mode.

        Args:
            mode_id: The mode ID to switch to (ask, auto, analyze)
            session_id: The session ID to update

        Returns:
            SetSessionModeResponse if successful

        Raises:
            RequestError: If mode_id is invalid
        """

        logger.info(f"Set session mode requested: {session_id} -> {mode_id}")

        mode = validate_confirmation_mode(mode_id)
        if mode is None:
            raise RequestError.invalid_params(
                {
                    "reason": f"Invalid mode ID: {mode_id}",
                    "validModes": sorted(VALID_CONFIRMATION_MODE),
                }
            )

        confirmation_mode: ConfirmationMode = cast(ConfirmationMode, mode_id)
        await self._set_confirmation_mode(session_id, confirmation_mode)

        await self._conn.session_update(
            session_id=session_id,
            update=update_current_mode(current_mode_id=mode_id),
        )

        return SetSessionModeResponse()

    async def _set_confirmation_mode(
        self, session_id: str, mode: ConfirmationMode
    ) -> None:
        """Set confirmation mode for a session.

        Args:
            session_id: The session ID
            mode: Confirmation mode (always-ask|always-approve|llm-approve)
        """
        if session_id in self._active_sessions:
            conversation = self._active_sessions[session_id]
            apply_confirmation_mode_to_conversation(conversation, mode, session_id)
            logger.debug(f"Confirmation mode for session {session_id}: {mode}")
        else:
            logger.warning(
                f"Cannot set confirmation mode for session {session_id}: "
                "session not found"
            )

    async def list_sessions(
        self,
        cursor: str | None = None,  # noqa: ARG002
        cwd: str | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> ListSessionsResponse:
        """List available sessions (no-op for now)."""
        logger.info("List sessions requested")
        return ListSessionsResponse(sessions=[])

    async def set_session_model(
        self,
        model_id: str,  # noqa: ARG002
        session_id: str,
        **_kwargs: Any,
    ) -> SetSessionModelResponse | None:
        """Set session model (no-op for now)."""
        logger.info(f"Set session model requested: {session_id}")
        return SetSessionModelResponse()

    async def authenticate(
        self, method_id: str, **_kwargs: Any
    ) -> AuthenticateResponse | None:
        """Authenticate the client (no-op for now)."""
        logger.info(f"Authentication requested with method: {method_id}")
        return AuthenticateResponse()

    def _get_or_create_conversation(
        self,
        session_id: str,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> RemoteConversation:
        """Get an active conversation from cache or create it with cloud workspace.

        Args:
            session_id: Session/conversation ID (UUID string)
            working_dir: Working directory (ignored for cloud workspace)
            mcp_servers: MCP servers config (only for new sessions)

        Returns:
            Cached or newly created conversation with cloud workspace
        """
        # Check if we already have this conversation active
        if session_id in self._active_sessions:
            logger.debug(f"Using cached cloud conversation for session {session_id}")
            return self._active_sessions[session_id]

        # Create new conversation with cloud workspace
        logger.debug(f"Creating new cloud conversation for session {session_id}")
        conversation, workspace = self._setup_cloud_conversation(
            session_id=session_id,
            mcp_servers=mcp_servers,
        )
        # Cache the conversation
        self._active_sessions[session_id] = conversation
        self._active_workspaces[session_id] = workspace

        return conversation

    def _setup_cloud_conversation(
        self,
        session_id: str,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[RemoteConversation, OpenHandsCloudWorkspace]:
        """Set up a conversation with OpenHands Cloud workspace.

        Args:
            session_id: Session/conversation ID (UUID string)
            mcp_servers: Optional MCP servers configuration

        Returns:
            Configured RemoteConversation with cloud workspace

        Raises:
            MissingAgentSpec: If agent configuration is missing
            RequestError: If MCP configuration is invalid
        """
        # Load agent specs
        try:
            agent = load_agent_specs(
                conversation_id=session_id,
                mcp_servers=mcp_servers,
                skills=[RESOURCE_SKILL],
            )
        except MCPConfigurationError as e:
            logger.error(f"Invalid MCP configuration: {e}")
            raise RequestError.invalid_params(
                {
                    "reason": "Invalid MCP configuration file",
                    "details": str(e),
                    "help": (
                        f"Please check ~/.openhands/{MCP_CONFIG_FILE} for "
                        "JSON syntax errors"
                    ),
                }
            )

        # Create OpenHands Cloud workspace
        logger.info(f"Creating OpenHands Cloud workspace for session {session_id}")
        workspace = OpenHandsCloudWorkspace(
            cloud_api_url=self._cloud_api_url,
            cloud_api_key=self._cloud_api_key,
            keep_alive=True,
        )

        # Track workspace for cleanup
        self._active_workspaces[session_id] = workspace

        # Get the current event loop for the callback
        loop = asyncio.get_event_loop()

        # Create event subscriber for streaming updates
        subscriber = EventSubscriber(session_id, self._conn)

        def sync_callback(event: Event) -> None:
            """Synchronous wrapper that schedules async event handling."""
            asyncio.run_coroutine_threadsafe(subscriber(event), loop)

        # Create RemoteConversation with cloud workspace
        # Note: RemoteConversation doesn't support persistence_dir
        conversation = Conversation(
            agent=agent, workspace=workspace, callbacks=[sync_callback]
        )

        subscriber.conversation = conversation
        return conversation, workspace

    async def new_session(
        self,
        cwd: str,  # noqa: ARG002
        mcp_servers: list[Any],
        **_kwargs: Any,
    ) -> NewSessionResponse:
        """Create a new conversation session with cloud workspace.

        Overrides the base implementation to handle cloud workspace creation.
        """
        # Use resume_conversation_id if provided (from --resume flag)
        # Only use it once, then clear it
        is_resuming = False
        if self._resume_conversation_id:
            session_id = self._resume_conversation_id
            self._resume_conversation_id = None
            is_resuming = True
            logger.info(f"Resuming conversation: {session_id}")
        else:
            session_id = str(uuid.uuid4())

        try:
            # Convert ACP MCP servers to Agent format
            mcp_servers_dict = None
            if mcp_servers:
                mcp_servers_dict = convert_acp_mcp_servers_to_agent_format(mcp_servers)

            # Note: working_dir is ignored for cloud workspace as it's managed
            # by the cloud environment
            logger.info(f"Creating cloud session {session_id}")

            # Create conversation with cloud workspace
            conversation = self._get_or_create_conversation(
                session_id=session_id,
                mcp_servers=mcp_servers_dict,
            )

            logger.info(f"Created new cloud session {session_id}")

            # Build response
            response = NewSessionResponse(
                session_id=session_id,
                modes=get_session_mode_state("always-approve"),
            )

            # If resuming, replay historic events to the client
            if is_resuming and conversation.state.events:
                logger.info(
                    f"Replaying {len(conversation.state.events)} historic events "
                    f"for resumed session {session_id}"
                )
                subscriber = EventSubscriber(session_id, self._conn)
                for event in conversation.state.events:
                    await subscriber(event)

            return response

        except MissingAgentSpec as e:
            logger.error(f"Agent not configured: {e}")
            raise RequestError.internal_error(
                {
                    "reason": "Agent not configured",
                    "details": "Please run 'openhands' to configure the agent first.",
                }
            )
        except RequestError:
            raise
        except Exception as e:
            logger.error(f"Failed to create new cloud session: {e}", exc_info=True)
            # Clean up workspace on failure
            self._cleanup_session(session_id)
            raise RequestError.internal_error(
                {"reason": "Failed to create new cloud session", "details": str(e)}
            )

    async def prompt(
        self, prompt: list[Any], session_id: str, **_kwargs: Any
    ) -> PromptResponse:
        """Handle a prompt request with cloud workspace."""
        try:
            # Get or create conversation (preserves state like pause/confirmation)
            conversation = self._get_or_create_conversation(session_id=session_id)

            # Convert ACP prompt format to OpenHands message content
            message_content = convert_acp_prompt_to_message_content(prompt)

            if not message_content:
                return PromptResponse(stop_reason="end_turn")

            # Send the message
            message = Message(role="user", content=message_content)
            conversation.send_message(message)

            async def send_message() -> None:
                conversation.run()

            # Run the conversation with confirmation mode
            run_task = asyncio.create_task(send_message())

            self._running_tasks[session_id] = run_task
            try:
                await run_task
            finally:
                self._running_tasks.pop(session_id, None)

            return PromptResponse(stop_reason="end_turn")

        except RequestError:
            raise
        except Exception as e:
            logger.error(f"Error processing prompt: {e}", exc_info=True)
            await self._conn.session_update(
                session_id=session_id,
                update=AgentMessageChunk(
                    session_update="agent_message_chunk",
                    content=TextContentBlock(type="text", text=f"Error: {str(e)}"),
                ),
            )
            raise RequestError.internal_error(
                {"reason": "Failed to process prompt", "details": str(e)}
            )

    async def load_session(
        self,
        cwd: str,  # noqa: ARG002
        mcp_servers: list[Any],  # noqa: ARG002
        session_id: str,
        **_kwargs: Any,
    ) -> LoadSessionResponse | None:
        """Load an existing session.

        Note: Cloud mode doesn't support persistent sessions in the same way
        as local mode. Each cloud session creates a new sandbox.
        """
        logger.info(f"Loading session: {session_id}")

        try:
            # Validate session ID format
            try:
                UUID(session_id)
            except ValueError:
                raise RequestError.invalid_params(
                    {"reason": "Invalid session ID format", "sessionId": session_id}
                )

            # For cloud mode, we can only load sessions that are already in memory
            if session_id in self._active_sessions:
                conversation = self._active_sessions[session_id]

                # Stream conversation history to client
                if conversation.state.events:
                    logger.info(
                        f"Streaming {len(conversation.state.events)} events from "
                        f"conversation history"
                    )
                    subscriber = EventSubscriber(session_id, self._conn)
                    for event in conversation.state.events:
                        await subscriber(event)

                current_mode = get_confirmation_mode_from_conversation(conversation)
                return LoadSessionResponse(modes=get_session_mode_state(current_mode))

            # Session not found - cloud mode doesn't support loading from disk
            raise RequestError.invalid_params(
                {
                    "reason": "Session not found",
                    "sessionId": session_id,
                    "help": (
                        "Cloud mode doesn't support loading sessions from disk. "
                        "Each cloud session creates a new sandbox."
                    ),
                }
            )

        except RequestError:
            raise
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}", exc_info=True)
            raise RequestError.internal_error(
                {"reason": "Failed to load session", "details": str(e)}
            )

    def _cleanup_session(self, session_id: str) -> None:
        """Clean up resources for a session.

        Args:
            session_id: The session ID to clean up
        """
        # Clean up workspace
        workspace = self._active_workspaces.pop(session_id, None)
        if workspace:
            try:
                workspace.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up workspace for {session_id}: {e}")

        # Clean up conversation
        conversation = self._active_sessions.pop(session_id, None)
        if conversation:
            try:
                conversation.close()
            except Exception as e:
                logger.warning(f"Error closing conversation for {session_id}: {e}")

    async def cancel(self, session_id: str, **_kwargs: Any) -> None:
        """Cancel the current operation."""
        logger.info(f"Cancel requested for session: {session_id}")

        pass

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Extension method (not supported)."""
        logger.info(f"Extension method '{method}' requested with params: {params}")
        return {"error": "ext_method not supported"}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Extension notification (no-op for now)."""
        logger.info(f"Extension notification '{method}' received with params: {params}")

    def on_connect(self, conn: Client) -> None:
        pass

    async def close_session(self, session_id: str, **_kwargs: Any) -> None:
        """Close a session and clean up resources."""
        logger.info(f"Closing cloud session: {session_id}")
        self._cleanup_session(session_id)

    def __del__(self) -> None:
        """Clean up all active workspaces on agent destruction."""
        for session_id in list(self._active_workspaces.keys()):
            self._cleanup_session(session_id)
