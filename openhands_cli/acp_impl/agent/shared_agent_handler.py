from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, cast

from acp import Client, InitializeResponse, NewSessionResponse, RequestError
from acp.helpers import update_current_mode
from acp.schema import (
    AgentCapabilities,
    AuthenticateResponse,
    AvailableCommandsUpdate,
    Implementation,
    ListSessionsResponse,
    McpCapabilities,
    PromptCapabilities,
    SetSessionModelResponse,
    SetSessionModeResponse,
    AuthMethod
)

from openhands.sdk import BaseConversation, LocalConversation, RemoteConversation
from openhands_cli import __version__
from openhands_cli.acp_impl.agent.util import AgentType, get_session_mode_state
from openhands_cli.acp_impl.confirmation import ConfirmationMode
from openhands_cli.acp_impl.events.event import EventSubscriber
from openhands_cli.acp_impl.slash_commands import (
    VALID_CONFIRMATION_MODE,
    apply_confirmation_mode_to_conversation,
    get_available_slash_commands,
    get_confirmation_mode_from_conversation,
    validate_confirmation_mode,
)
from openhands_cli.acp_impl.utils import convert_acp_mcp_servers_to_agent_format
from openhands_cli.setup import MissingAgentSpec, load_agent_specs


if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class _ACPAgentContext(Protocol):
    """Protocol defining the interface for ACP agent context.

    This allows SharedACPAgentHandler to work with any class that has these
    attributes, similar to how SharedEventHandler uses _ACPContext.
    """

    _conn: Client
    _running_tasks: dict[str, asyncio.Task]
    _resume_conversation_id: str | None
    agent_type: AgentType

    @property
    def active_session(self) -> Mapping[str, BaseConversation]:
        """Return the active sessions mapping."""
        ...

    def _get_or_create_conversation(
        self,
        session_id: str,
        working_dir: str | None = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> BaseConversation:
        """Get or create a conversation for the given session ID."""
        ...

    def _cleanup_session(self, session_id: str) -> None:
        """Clean up resources for a session (optional, may be no-op)."""
        ...


class SharedACPAgentHandler:
    """Shared ACP agent behavior used by both local and cloud agents."""

    def __init__(self, conn: Client):
        self._conn = conn

    async def send_available_commands(self, session_id: str) -> None:
        """Send available slash commands to the client.

        Args:
            session_id: The session ID
        """
        await self._conn.session_update(
            session_id=session_id,
            update=AvailableCommandsUpdate(
                session_update="available_commands_update",
                available_commands=get_available_slash_commands(),
            ),
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
            auth_methods = [AuthMethod(description="OAuth with OpenHands Cloud", id="oauth", name="OAuth")]
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

    async def authenticate(
        self, method_id: str, **_kwargs: Any
    ) -> AuthenticateResponse | None:
        """Authenticate the client (no-op for now)."""
        logger.info(f"Authentication requested with method: {method_id}")
        return AuthenticateResponse()

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

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Extension method (not supported)."""
        logger.info(f"Extension method '{method}' requested with params: {params}")
        return {"error": "ext_method not supported"}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Extension notification (no-op for now)."""
        logger.info(f"Extension notification '{method}' received with params: {params}")

    async def set_confirmation_mode(
        self, ctx: _ACPAgentContext, session_id: str, mode: ConfirmationMode
    ) -> None:
        """Set confirmation mode for a session.

        Args:
            ctx: The ACP agent context
            session_id: The session ID
            mode: Confirmation mode (always-ask|always-approve|llm-approve)
        """
        if session_id in ctx.active_session:
            conversation = ctx.active_session[session_id]
            # Cast to the union type expected by apply_confirmation_mode_to_conversation
            typed_conversation = cast(
                LocalConversation | RemoteConversation, conversation
            )
            apply_confirmation_mode_to_conversation(
                typed_conversation, mode, session_id
            )
            logger.debug(f"Confirmation mode for session {session_id}: {mode}")
        else:
            logger.warning(
                f"Cannot set confirmation mode for session {session_id}: "
                "session not found"
            )

    async def set_session_mode(
        self,
        ctx: _ACPAgentContext,
        mode_id: str,
        session_id: str,
        **_kwargs: Any,
    ) -> SetSessionModeResponse | None:
        """Set session mode by updating confirmation mode.

        Args:
            ctx: The ACP agent context
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
        await self.set_confirmation_mode(ctx, session_id, confirmation_mode)

        await ctx._conn.session_update(
            session_id=session_id,
            update=update_current_mode(current_mode_id=mode_id),
        )

        return SetSessionModeResponse()

    async def new_session(
        self,
        ctx: _ACPAgentContext,
        mcp_servers: list[Any],
        working_dir: str | None = None,
    ) -> NewSessionResponse:
        """Create a new conversation session.

        This shared method handles the common logic for creating sessions in both
        local and cloud agents.

        Args:
            ctx: The ACP agent context
            mcp_servers: ACP MCP servers configuration (will be converted)
            working_dir: Working directory for local sessions (ignored for cloud)

        Returns:
            NewSessionResponse with session ID and modes
        """
        # Determine session type name from agent type
        session_type_name = "cloud session" if ctx.agent_type == "remote" else "session"

        # Convert ACP MCP servers to Agent format
        mcp_servers_dict = None
        if mcp_servers:
            mcp_servers_dict = convert_acp_mcp_servers_to_agent_format(mcp_servers)

        # Use resume_conversation_id if provided (from --resume flag)
        # Only use it once, then clear it
        is_resuming = False
        if ctx._resume_conversation_id:
            session_id = ctx._resume_conversation_id
            ctx._resume_conversation_id = None
            is_resuming = True
            logger.info(f"Resuming conversation: {session_id}")
        else:
            session_id = str(uuid.uuid4())

        try:
            # Create conversation and cache it for future operations
            conversation = ctx._get_or_create_conversation(
                session_id=session_id,
                working_dir=working_dir,
                mcp_servers=mcp_servers_dict,
            )

            logger.info(f"Created new {session_type_name} {session_id}")

            # Send available slash commands to client
            await self.send_available_commands(session_id)

            # Get current confirmation mode for this session
            current_mode = get_confirmation_mode_from_conversation(conversation)

            # Build response first (before streaming events)
            response = NewSessionResponse(
                session_id=session_id,
                modes=get_session_mode_state(current_mode),
            )

            # If resuming, replay historic events to the client
            # This ensures the ACP client sees the full conversation history
            if is_resuming and conversation.state.events:
                logger.info(
                    f"Replaying {len(conversation.state.events)} historic events "
                    f"for resumed session {session_id}"
                )
                subscriber = EventSubscriber(session_id, ctx._conn)
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
            # Re-raise RequestError as-is
            raise
        except Exception as e:
            logger.error(
                f"Failed to create new {session_type_name}: {e}", exc_info=True
            )
            # Clean up on failure
            ctx._cleanup_session(session_id)
            raise RequestError.internal_error(
                {
                    "reason": f"Failed to create new {session_type_name}",
                    "details": str(e),
                }
            )

    async def wait_for_task_completion(
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

    async def cancel(
        self,
        ctx: _ACPAgentContext,
        session_id: str,
        get_or_create_conversation: Any,
        **_kwargs: Any,
    ) -> None:
        """Cancel the current operation.

        Args:
            ctx: The ACP agent context
            session_id: The session ID to cancel
            get_or_create_conversation: Callable to get or create conversation
        """
        logger.info(f"Cancel requested for session: {session_id}")

        try:
            conversation = get_or_create_conversation(session_id=session_id)
            conversation.pause()

            running_task = ctx._running_tasks.get(session_id)
            if not running_task or running_task.done():
                return

            logger.debug(
                f"Waiting for conversation thread to terminate for session {session_id}"
            )
            await self.wait_for_task_completion(running_task, session_id)

        except RequestError:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel session {session_id}: {e}")
            raise RequestError.internal_error(
                {"reason": "Failed to cancel session", "details": str(e)}
            )
