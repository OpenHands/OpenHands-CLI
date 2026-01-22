"""OpenHands Cloud ACP Agent implementation."""

import asyncio
import logging
from typing import Any
from uuid import UUID

from acp import Client, NewSessionResponse, PromptResponse, RequestError
from acp.schema import AuthenticateResponse, LoadSessionResponse

from openhands.sdk import BaseConversation, Conversation, Event, RemoteConversation
from openhands.workspace import OpenHandsCloudWorkspace
from openhands_cli.acp_impl.agent.base_agent import BaseOpenHandsACPAgent
from openhands_cli.acp_impl.agent.util import AgentType, get_session_mode_state
from openhands_cli.acp_impl.confirmation import ConfirmationMode
from openhands_cli.acp_impl.events.event import EventSubscriber
from openhands_cli.acp_impl.slash_commands import (
    apply_confirmation_mode_to_conversation,
    get_confirmation_mode_from_conversation,
)
from openhands_cli.acp_impl.utils import RESOURCE_SKILL
from openhands_cli.auth.api_client import (
    ApiClientError,
    OpenHandsApiClient,
    UnauthenticatedError,
)
from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.auth.utils import is_token_valid
from openhands_cli.locations import MCP_CONFIG_FILE
from openhands_cli.mcp.mcp_utils import MCPConfigurationError
from openhands_cli.setup import load_agent_specs


logger = logging.getLogger(__name__)


class OpenHandsCloudACPAgent(BaseOpenHandsACPAgent):
    """OpenHands Cloud ACP Agent that uses OpenHands Cloud for sandbox environments."""

    def __init__(
        self,
        conn: Client,
        initial_confirmation_mode: ConfirmationMode,
        cloud_api_url: str = "https://app.all-hands.dev",
        resume_conversation_id: str | None = None,
    ):
        """Initialize the cloud ACP agent.

        Args:
            conn: ACP connection for sending notifications
            initial_confirmation_mode: Default confirmation mode for new sessions
            cloud_api_url: OpenHands Cloud API URL
            resume_conversation_id: Optional conversation ID to resume
        """
        super().__init__(conn, initial_confirmation_mode, resume_conversation_id)

        self.store = TokenStorage()
        self._cloud_api_key = self.store.get_api_key()
        self._cloud_api_url = cloud_api_url

        self._active_workspaces: dict[str, OpenHandsCloudWorkspace] = {}

        logger.info(
            f"OpenHands Cloud ACP Agent initialized with cloud URL: {cloud_api_url}"
        )

    @property
    def agent_type(self) -> AgentType:
        """Return the agent type."""
        return "remote"

    async def _is_authenticated(self) -> bool:
        """Check if the user is authenticated with OpenHands Cloud."""
        if not self._cloud_api_key:
            return False

        return await is_token_valid(
            server_url=self._cloud_api_url, api_key=self._cloud_api_key
        )

    def _cleanup_session(self, session_id: str) -> None:
        """Clean up resources for a session."""
        workspace = self._active_workspaces.pop(session_id, None)
        if workspace:
            try:
                workspace.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up workspace for {session_id}: {e}")

        conversation = self._active_sessions.pop(session_id, None)
        if conversation:
            try:
                conversation.close()
            except Exception as e:
                logger.warning(f"Error closing conversation for {session_id}: {e}")

    async def authenticate(
        self, method_id: str, **_kwargs: Any
    ) -> AuthenticateResponse | None:
        """Authenticate the client using OAuth2 device flow."""
        logger.info(f"Authentication requested with method: {method_id}")

        if method_id != "oauth":
            raise RequestError.invalid_params(
                {"reason": f"Unsupported authentication method: {method_id}"}
            )

        from openhands_cli.auth.device_flow import DeviceFlowError
        from openhands_cli.auth.login_command import login_command

        try:
            await login_command(self._cloud_api_url, skip_settings_sync=True)
            self._cloud_api_key = self.store.get_api_key()
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
        """Verify a conversation exists and get its sandbox_id."""
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
        is_resuming: bool = False,
    ) -> BaseConversation:
        """Get an active conversation from cache or create it with cloud workspace."""
        # Skip cache check when resuming to recreate workspace
        if session_id in self._active_sessions and not is_resuming:
            logger.debug(f"Using cached cloud conversation for session {session_id}")
            return self._active_sessions[session_id]

        sandbox_id: str | None = None
        if is_resuming:
            logger.info(
                f"Resuming conversation {session_id}, "
                "verifying and getting sandbox_id..."
            )
            sandbox_id = await self._verify_and_get_sandbox_id(session_id)

        logger.debug(f"Creating new cloud conversation for session {session_id}")
        conversation, workspace = self._setup_conversation(
            session_id=session_id,
            mcp_servers=mcp_servers,
            sandbox_id=sandbox_id,
        )

        apply_confirmation_mode_to_conversation(
            conversation, self._initial_confirmation_mode, session_id
        )

        self._active_sessions[session_id] = conversation
        self._active_workspaces[session_id] = workspace

        return conversation

    def _setup_conversation(
        self,
        session_id: str,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
        sandbox_id: str | None = None,
    ) -> tuple[RemoteConversation, OpenHandsCloudWorkspace]:
        """Set up a conversation with OpenHands Cloud workspace."""
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

        self._active_workspaces[session_id] = workspace

        loop = asyncio.get_event_loop()
        subscriber = EventSubscriber(session_id, self._conn)

        def sync_callback(event: Event) -> None:
            asyncio.run_coroutine_threadsafe(subscriber(event), loop)

        conversation = Conversation(
            agent=agent,
            workspace=workspace,
            callbacks=[sync_callback],
            conversation_id=UUID(session_id),
        )

        subscriber.conversation = conversation
        return conversation, workspace

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[Any],
        working_dir: str | None = None,
        **_kwargs: Any,
    ) -> NewSessionResponse:
        """Create a new conversation session with cloud workspace."""
        is_authenticated = await self._is_authenticated()
        if not is_authenticated:
            logger.info("User not authenticated, requiring authentication")
            raise RequestError.auth_required(
                {"reason": "Authentication required to create a cloud session"}
            )

        return await super().new_session(
            cwd=cwd, mcp_servers=mcp_servers, working_dir=working_dir, **_kwargs
        )

    async def prompt(
        self, prompt: list[Any], session_id: str, **_kwargs: Any
    ) -> PromptResponse:
        """Handle a prompt request with cloud workspace.

        Overrides base class to handle workspace resuming when workspace is not alive.
        """
        # Check if workspace needs to be resumed
        workspace = self._active_workspaces.get(session_id)
        if not workspace:
            raise RequestError.internal_error(
                {"reason": "Missing workspace for session"}
            )

        # Resume workspace if it's not alive
        is_resuming = not workspace.alive
        if is_resuming:
            # Force recreation of conversation with resumed workspace
            await self._get_or_create_conversation(
                session_id=session_id, is_resuming=True
            )

        # Call base class prompt implementation
        return await super().prompt(prompt, session_id, **_kwargs)

    async def load_session(
        self,
        cwd: str,  # noqa: ARG002
        mcp_servers: list[Any],  # noqa: ARG002
        session_id: str,
        **_kwargs: Any,
    ) -> LoadSessionResponse | None:
        """Load an existing session (cloud mode has limited support)."""
        logger.info(f"Loading session: {session_id}")

        try:
            try:
                UUID(session_id)
            except ValueError:
                raise RequestError.invalid_params(
                    {"reason": "Invalid session ID format", "sessionId": session_id}
                )

            # For cloud mode, we can only load sessions that are already in memory
            if session_id in self._active_sessions:
                conversation = self._active_sessions[session_id]

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

    async def close_session(self, session_id: str, **_kwargs: Any) -> None:
        """Close a session and clean up resources."""
        logger.info(f"Closing cloud session: {session_id}")
        self._cleanup_session(session_id)

    def __del__(self) -> None:
        """Clean up all active workspaces on agent destruction."""
        for session_id in list(self._active_workspaces.keys()):
            self._cleanup_session(session_id)
