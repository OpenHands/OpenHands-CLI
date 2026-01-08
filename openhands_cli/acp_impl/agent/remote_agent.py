"""OpenHands Cloud ACP Agent implementation.

This module provides the ACP agent implementation that uses OpenHands Cloud
for sandbox environments instead of local workspace.
"""

import asyncio
import logging
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
    SessionInfo,
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
from openhands_cli.acp_impl.agent.shared_agent_handler import SharedACPAgentHandler
from openhands_cli.acp_impl.agent.util import AgentType, get_session_mode_state
from openhands_cli.acp_impl.confirmation import (
    ConfirmationMode,
)
from openhands_cli.acp_impl.events.event import EventSubscriber
from openhands_cli.acp_impl.runner import run_conversation_with_confirmation
from openhands_cli.acp_impl.slash_commands import (
    apply_confirmation_mode_to_conversation,
    get_confirmation_mode_from_conversation,
)
from openhands_cli.acp_impl.utils import (
    RESOURCE_SKILL,
    convert_acp_prompt_to_message_content,
)
from openhands_cli.auth.api_client import (
    ApiClientError,
    OpenHandsApiClient,
    UnauthenticatedError,
)
from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.cloud.conversation import is_token_valid
from openhands_cli.locations import MCP_CONFIG_FILE
from openhands_cli.mcp.mcp_utils import MCPConfigurationError
from openhands_cli.setup import load_agent_specs


logger = logging.getLogger(__name__)


class OpenHandsCloudACPAgent(ACPAgent):
    """OpenHands Cloud ACP Agent that uses OpenHands Cloud for sandbox environments.

    This agent connects to OpenHands Cloud (app.all-hands.dev) to provision
    sandboxed environments for agent execution instead of using local workspace.
    """

    def __init__(
        self,
        conn: Client,
        initial_confirmation_mode: ConfirmationMode,
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

        self.store = TokenStorage()
        self._cloud_api_key = self.store.get_api_key()
        self._cloud_api_url = cloud_api_url

        # Track active cloud workspaces for cleanup
        self._active_sessions: dict[str, RemoteConversation] = {}
        self._active_workspaces: dict[str, OpenHandsCloudWorkspace] = {}

        self._initial_confirmation_mode: ConfirmationMode = initial_confirmation_mode

        logger.info(
            f"OpenHands Cloud ACP Agent initialized with cloud URL: {cloud_api_url}"
        )

        self.agent_type: AgentType = "remote"

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
        cursor: str | None = None,  # noqa: ARG002
        cwd: str | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> ListSessionsResponse:
        """List available cloud sessions (V1 conversations only)."""
        logger.info("List sessions requested for cloud agent")

        if not self._cloud_api_key:
            logger.warning("No API key available, returning empty session list")
            return ListSessionsResponse(sessions=[])

        try:
            client = OpenHandsApiClient(self._cloud_api_url, self._cloud_api_key)
            conversations = await client.list_conversations()

            # Filter to only V1 conversations and convert to SessionInfo
            sessions: list[SessionInfo] = []
            for conv in conversations:
                if conv.get("conversation_version") != "V1":
                    continue

                session_info = SessionInfo(
                    session_id=conv.get("conversation_id", ""),
                    cwd="/",  # Cloud sessions don't have a local cwd
                    title=conv.get("title"),
                    updated_at=conv.get("last_updated_at"),
                )
                sessions.append(session_info)

            logger.info(f"Found {len(sessions)} V1 cloud sessions")
            return ListSessionsResponse(sessions=sessions)

        except UnauthenticatedError:
            logger.warning("Authentication failed, returning empty session list")
            return ListSessionsResponse(sessions=[])
        except ApiClientError as e:
            logger.error(f"Failed to list sessions: {e}")
            return ListSessionsResponse(sessions=[])

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
        """Authenticate the client using OAuth2 device flow.

        This method performs the OAuth2 device flow to authenticate the user
        with OpenHands Cloud. It opens a browser for the user to authorize,
        then stores the resulting API key for future requests.

        Args:
            method_id: Authentication method ID (should be "oauth")

        Returns:
            AuthenticateResponse on success

        Raises:
            RequestError: If authentication fails
        """
        logger.info(f"Authentication requested with method: {method_id}")

        if method_id != "oauth":
            raise RequestError.invalid_params(
                {"reason": f"Unsupported authentication method: {method_id}"}
            )

        from openhands_cli.auth.api_client import (
            ApiClientError,
            fetch_user_data_after_oauth,
        )
        from openhands_cli.auth.device_flow import (
            DeviceFlowError,
            authenticate_with_device_flow,
        )

        try:
            # Perform OAuth2 device flow authentication
            tokens = await authenticate_with_device_flow(self._cloud_api_url)

            api_key = tokens.get("access_token")
            if not api_key:
                raise RequestError.internal_error(
                    {"reason": "No access token received from OAuth flow"}
                )

            # Store the API key
            store = TokenStorage()
            store.store_api_key(api_key)

            # Update the agent's API key
            self._cloud_api_key = api_key

            # Fetch user data and configure the agent
            try:
                await fetch_user_data_after_oauth(self._cloud_api_url, api_key)
            except ApiClientError as e:
                # Log - auth succeeded even if data fetch failed
                logger.warning(f"Failed to fetch user data after OAuth: {e}")

            logger.info("OAuth authentication completed successfully")
            return AuthenticateResponse()

        except DeviceFlowError as e:
            logger.error(f"OAuth authentication failed: {e}")
            raise RequestError.internal_error(
                {"reason": f"Authentication failed: {e}"}
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}", exc_info=True)
            raise RequestError.internal_error(
                {"reason": f"Authentication error: {e}"}
            ) from e

    async def _verify_and_get_sandbox_id(self, conversation_id: str) -> str:
        """Verify a conversation exists and get its sandbox_id.

        Args:
            conversation_id: The conversation ID to verify

        Returns:
            The sandbox_id associated with the conversation

        Raises:
            RequestError: If the conversation doesn't exist or has no sandbox_id
        """
        if not self._cloud_api_key:
            raise RequestError.auth_required(
                {"reason": "Authentication required to verify conversation"}
            )

        logger.info(f"Verifying conversation {conversation_id} exists...")

        try:
            client = OpenHandsApiClient(self._cloud_api_url, self._cloud_api_key)
            conversation_info = await client.get_conversation_info(conversation_id)
        except UnauthenticatedError:
            raise RequestError.auth_required(
                {"reason": "Authentication required to verify conversation"}
            )
        except ApiClientError as e:
            if "HTTP 404" in str(e):
                raise RequestError.invalid_params(
                    {
                        "reason": "Conversation not found",
                        "conversation_id": conversation_id,
                        "help": (
                            "The conversation may have been deleted "
                            "or the ID is incorrect."
                        ),
                    }
                )
            logger.error(f"Failed to verify conversation: {e}")
            raise RequestError.internal_error(
                {"reason": f"Failed to verify conversation: {e}"}
            )
        except Exception as e:
            logger.error(f"Error verifying conversation: {e}", exc_info=True)
            raise RequestError.internal_error(
                {"reason": f"Error verifying conversation: {e}"}
            )

        sandbox_id = conversation_info.get("sandbox_id") if conversation_info else None
        if not sandbox_id:
            raise RequestError.invalid_params(
                {
                    "reason": "Conversation has no associated sandbox",
                    "conversation_id": conversation_id,
                    "help": (
                        "The conversation may not have been started with a sandbox."
                    ),
                }
            )

        logger.info(f"Found sandbox_id {sandbox_id} for conversation {conversation_id}")
        return sandbox_id

    async def _get_or_create_conversation(
        self,
        session_id: str,
        working_dir: str | None = None,  # noqa: ARG002
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

        # Check if we're resuming a conversation
        sandbox_id: str | None = None
        if self._resume_conversation_id:
            logger.info(
                f"Resuming conversation {session_id}, "
                "verifying and getting sandbox_id..."
            )
            sandbox_id = await self._verify_and_get_sandbox_id(session_id)

        # Create new conversation with cloud workspace
        logger.debug(f"Creating new cloud conversation for session {session_id}")
        conversation, workspace = self._setup_cloud_conversation(
            session_id=session_id,
            mcp_servers=mcp_servers,
            sandbox_id=sandbox_id,
        )

        apply_confirmation_mode_to_conversation(
            conversation, self._initial_confirmation_mode, session_id
        )

        # Cache the conversation
        self._active_sessions[session_id] = conversation
        self._active_workspaces[session_id] = workspace

        return conversation

    def _setup_cloud_conversation(
        self,
        session_id: str,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
        sandbox_id: str | None = None,
    ) -> tuple[RemoteConversation, OpenHandsCloudWorkspace]:
        """Set up a conversation with OpenHands Cloud workspace.

        Args:
            session_id: Session/conversation ID (UUID string)
            mcp_servers: Optional MCP servers configuration
            sandbox_id: Optional sandbox ID to resume an existing sandbox

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
        if sandbox_id:
            logger.info(
                f"Resuming OpenHands Cloud workspace with sandbox_id {sandbox_id} "
                f"for session {session_id}"
            )
        else:
            logger.info(f"Creating OpenHands Cloud workspace for session {session_id}")

        if not self._cloud_api_key:
            raise RequestError.auth_required(
                {"reason": "Authentication required to create a cloud session"}
            )

        workspace = OpenHandsCloudWorkspace(
            cloud_api_url=self._cloud_api_url,
            cloud_api_key=self._cloud_api_key,
            keep_alive=True,
            sandbox_id=sandbox_id,
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
            agent=agent,
            workspace=workspace,
            callbacks=[sync_callback],
            conversation_id=UUID(session_id),
        )

        subscriber.conversation = conversation
        return conversation, workspace

    async def _is_authenticated(self) -> bool:
        """Check if the user is authenticated with OpenHands Cloud.

        Returns:
            True if the user has a valid API key stored, False otherwise.
        """

        if not self._cloud_api_key:
            return False

        return await is_token_valid(
            server_url=self._cloud_api_url, api_key=self._cloud_api_key
        )

    async def new_session(
        self,
        cwd: str,  # noqa: ARG002
        mcp_servers: list[Any],
        **_kwargs: Any,
    ) -> NewSessionResponse:
        """Create a new conversation session with cloud workspace.

        Overrides the base implementation to handle cloud workspace creation.
        Note: working_dir is ignored for cloud workspace as it's managed
        by the cloud environment.

        Raises:
            RequestError.auth_required: If the user is not authenticated
        """
        # Check if user is authenticated before creating a session
        is_authenticated = await self._is_authenticated()
        if not is_authenticated:
            logger.info("User not authenticated, requiring authentication")
            raise RequestError.auth_required(
                {"reason": "Authentication required to create a cloud session"}
            )

        return await self._shared_handler.new_session(
            ctx=self,
            mcp_servers=mcp_servers,
            get_or_create_conversation=self._get_or_create_conversation,
        )

    async def prompt(
        self, prompt: list[Any], session_id: str, **_kwargs: Any
    ) -> PromptResponse:
        """Handle a prompt request with cloud workspace."""
        try:
            # Get or create conversation (preserves state like pause/confirmation)
            conversation = await self._get_or_create_conversation(session_id=session_id)

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

            # Send the message with potentially multiple content types
            # (text + images)
            message = Message(role="user", content=message_content)
            conversation.send_message(message)

            # Run the conversation with confirmation mode via runner function
            # The runner handles the confirmation flow for all modes
            # Track the running task so cancel() can wait for proper cleanup
            run_task = asyncio.create_task(
                run_conversation_with_confirmation(
                    conversation=conversation,
                    conn=self._conn,
                    session_id=session_id,
                )
            )

            self._running_tasks[session_id] = run_task
            try:
                await run_task
            finally:
                # Clean up task tracking and streaming state
                self._running_tasks.pop(session_id, None)

            # Return the final response
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
