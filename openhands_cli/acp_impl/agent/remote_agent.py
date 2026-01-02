"""OpenHands Cloud ACP Agent implementation.

This module provides the ACP agent implementation that uses OpenHands Cloud
for sandbox environments instead of local workspace.
"""

import asyncio
import logging
import uuid
from typing import Any
from uuid import UUID

from acp import (
    Agent as ACPAgent,
    Client,
    InitializeResponse,
    NewSessionResponse,
    PromptResponse,
    RequestError,
)
from acp.schema import (
    AgentMessageChunk,
    AuthenticateResponse,
    ListSessionsResponse,
    LoadSessionResponse,
    SetSessionModelResponse,
    SetSessionModeResponse,
    TextContentBlock,
)
from rich.console import Console

from openhands.sdk import (
    Conversation,
    Event,
    Message,
    RemoteConversation,
)
from openhands.workspace import OpenHandsCloudWorkspace
from openhands_cli.acp_impl.agent.shared_agent_handler import SharedACPAgentHandler
from openhands_cli.acp_impl.agent.util import get_session_mode_state
from openhands_cli.acp_impl.events.event import EventSubscriber
from openhands_cli.acp_impl.slash_commands import (
    get_confirmation_mode_from_conversation,
)
from openhands_cli.acp_impl.utils import (
    RESOURCE_SKILL,
    convert_acp_mcp_servers_to_agent_format,
    convert_acp_prompt_to_message_content,
)
from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.cloud.conversation import is_token_valid
from openhands_cli.locations import MCP_CONFIG_FILE
from openhands_cli.mcp.mcp_utils import MCPConfigurationError
from openhands_cli.setup import MissingAgentSpec, load_agent_specs
from openhands_cli.theme import OPENHANDS_THEME


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
            cloud_api_key: API key for OpenHands Cloud authentication
            cloud_api_url: OpenHands Cloud API URL
            resume_conversation_id: Optional conversation ID to resume
        """
        self._conn = conn
        self._shared_handler = SharedACPAgentHandler(conn)
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

    @property
    def active_session(self) -> dict[str, RemoteConversation]:
        """Return the active sessions mapping."""
        return self._active_sessions

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: Any | None = None,
        client_info: Any | None = None,
        **_kwargs: Any,
    ) -> InitializeResponse:
        """Initialize the ACP protocol."""
        return await self._shared_handler.initialize(
            protocol_version, client_capabilities, client_info, **_kwargs
        )

    async def set_session_mode(
        self,
        mode_id: str,
        session_id: str,
        **_kwargs: Any,
    ) -> SetSessionModeResponse | None:
        """Set session mode by updating confirmation mode."""
        return await self._shared_handler.set_session_mode(
            self, mode_id, session_id, **_kwargs
        )

    async def list_sessions(
        self,
        cursor: str | None = None,
        cwd: str | None = None,
        **_kwargs: Any,
    ) -> ListSessionsResponse:
        """List available sessions (no-op for now)."""
        return await self._shared_handler.list_sessions(cursor, cwd, **_kwargs)

    async def set_session_model(
        self,
        model_id: str,
        session_id: str,
        **_kwargs: Any,
    ) -> SetSessionModelResponse | None:
        """Set session model (no-op for now)."""
        return await self._shared_handler.set_session_model(
            model_id, session_id, **_kwargs
        )

    async def authenticate(
        self, method_id: str, **_kwargs: Any
    ) -> AuthenticateResponse | None:
        """Authenticate the client (no-op for now)."""
        return await self._shared_handler.authenticate(method_id, **_kwargs)

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

            await self._shared_handler.send_available_commands(session_id)

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
        await self._shared_handler.cancel(
            self, session_id, self._get_or_create_conversation, **_kwargs
        )

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Extension method (not supported)."""
        return await self._shared_handler.ext_method(method, params)

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Extension notification (no-op for now)."""
        await self._shared_handler.ext_notification(method, params)

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
