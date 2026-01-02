from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, cast

from acp import Client, InitializeResponse, RequestError
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
)

from openhands.sdk import BaseConversation, LocalConversation, RemoteConversation
from acp_impl.agent.util import AgentType
from openhands_cli import __version__
from openhands_cli.acp_impl.confirmation import ConfirmationMode
from openhands_cli.acp_impl.slash_commands import (
    VALID_CONFIRMATION_MODE,
    apply_confirmation_mode_to_conversation,
    get_available_slash_commands,
    validate_confirmation_mode,
)
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
    agent_type: AgentType

    @property
    def active_session(self) -> Mapping[str, BaseConversation]:
        """Return the active sessions mapping."""
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
