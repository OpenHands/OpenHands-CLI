"""Base OpenHands ACP Agent implementation.

This module provides the abstract base class for ACP agents, implementing
common functionality shared between local and cloud agents.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping
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
    AuthMethod,
    AvailableCommandsUpdate,
    ForkSessionResponse,
    Implementation,
    ListSessionsResponse,
    LoadSessionResponse,
    McpCapabilities,
    PromptCapabilities,
    ResumeSessionResponse,
    SetSessionConfigOptionResponse,
    SetSessionModelResponse,
    SetSessionModeResponse,
    TextContentBlock,
)

from openhands.sdk import (
    BaseConversation,
    Message,
)
from openhands.sdk.event.base import Event
from openhands_cli import __version__
from openhands_cli.acp_impl.agent.util import AgentType, get_session_mode_state
from openhands_cli.acp_impl.confirmation import ConfirmationMode
from openhands_cli.acp_impl.events.event import EventSubscriber
from openhands_cli.acp_impl.runner import run_conversation_with_confirmation
from openhands_cli.acp_impl.slash_commands import (
    VALID_CONFIRMATION_MODE,
    apply_confirmation_mode_to_conversation,
    create_help_text,
    get_available_slash_commands,
    get_confirmation_mode_from_conversation,
    get_unknown_command_text,
    handle_confirm_argument,
    parse_slash_command,
    validate_confirmation_mode,
)
from openhands_cli.acp_impl.utils import (
    convert_acp_mcp_servers_to_agent_format,
    convert_acp_prompt_to_message_content,
)
from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.setup import MissingAgentSpec
from openhands_cli.utils import extract_text_from_message_content


logger = logging.getLogger(__name__)


class BaseOpenHandsACPAgent(ACPAgent, ABC):
    """Abstract base class for OpenHands ACP agents.

    This class implements common functionality shared between local and cloud agents,
    including:
    - Initialization and protocol handling
    - Slash command processing
    - Prompt handling with confirmation mode
    - Session management

    Subclasses must implement:
    - agent_type property: Return "local" or "remote"
    - _setup_conversation(): Create and configure a conversation
    - _cleanup_session(): Clean up resources for a session
    - _is_authenticated(): Check if user is authenticated (for cloud)
    - _get_or_create_conversation(): Get cached or create new conversation
    """

    def __init__(
        self,
        conn: Client,
        initial_confirmation_mode: ConfirmationMode,
        resume_conversation_id: str | None = None,
        cloud_api_url: str = "https://app.all-hands.dev",
    ) -> None:
        """Initialize the base ACP agent.

        Args:
            conn: ACP connection for sending notifications
            initial_confirmation_mode: Default confirmation mode for new sessions
            resume_conversation_id: Optional conversation ID to resume
            cloud_api_url: OpenHands Cloud API URL for authentication
        """
        self._conn = conn
        self._active_sessions: dict[str, BaseConversation] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._initial_confirmation_mode: ConfirmationMode = initial_confirmation_mode
        self._resume_conversation_id: str | None = resume_conversation_id

        # Auth-related state
        self._store = TokenStorage()
        self._cloud_api_url = cloud_api_url
        self._cloud_api_key: str | None = self._store.get_api_key()

        if resume_conversation_id:
            logger.info(f"Will resume conversation: {resume_conversation_id}")

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """Return the agent type ('local' or 'remote')."""
        ...

    @property
    def active_sessions(self) -> Mapping[str, BaseConversation]:
        """Return the active sessions mapping."""
        return self._active_sessions

    @abstractmethod
    async def _get_or_create_conversation(
        self,
        session_id: str,
        working_dir: str | None = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
        is_resuming: bool = False,
    ) -> BaseConversation:
        """Get an active conversation from cache or create a new one.

        Args:
            session_id: Session/conversation ID (UUID string)
            working_dir: Working directory for workspace (local only)
            mcp_servers: MCP servers config (only for new sessions)
            is_resuming: Whether this is resuming an existing conversation

        Returns:
            Cached or newly created conversation
        """
        ...

    @abstractmethod
    def _cleanup_session(self, session_id: str) -> None:
        """Clean up resources for a session.

        Args:
            session_id: The session ID to clean up
        """
        ...

    @abstractmethod
    async def _is_authenticated(self) -> bool:
        """Check if the user is authenticated.

        Returns:
            True if authenticated, False otherwise.
        """
        ...

    def on_connect(self, conn: Client) -> None:  # noqa: ARG002
        """Handle connection event (no-op by default)."""
        pass

    async def send_available_commands(self, session_id: str) -> None:
        """Send available slash commands to the client."""
        await self._conn.session_update(
            session_id=session_id,
            update=AvailableCommandsUpdate(
                session_update="available_commands_update",
                available_commands=get_available_slash_commands(),
            ),
        )

    async def _set_confirmation_mode(
        self, session_id: str, mode: ConfirmationMode
    ) -> None:
        """Set confirmation mode for a session."""
        if session_id in self._active_sessions:
            conversation = self._active_sessions[session_id]
            apply_confirmation_mode_to_conversation(conversation, mode, session_id)
            logger.debug(f"Confirmation mode for session {session_id}: {mode}")
        else:
            logger.warning(
                f"Cannot set confirmation mode for session {session_id}: "
                "session not found"
            )

    async def _cmd_confirm(self, session_id: str, argument: str) -> str:
        """Handle /confirm command.

        Args:
            session_id: The session ID
            argument: Command argument (always-ask|always-approve|llm-approve)

        Returns:
            Status message
        """
        if session_id in self._active_sessions:
            current_mode = get_confirmation_mode_from_conversation(
                self._active_sessions[session_id]
            )
        else:
            current_mode = self._initial_confirmation_mode

        response_text, new_mode = handle_confirm_argument(current_mode, argument)
        if new_mode is not None:
            await self._set_confirmation_mode(session_id, new_mode)

        return response_text

    def _get_new_session_context(self) -> tuple[str, bool]:
        """Return the next session ID and whether it resumes a conversation."""
        if self._resume_conversation_id:
            session_id = self._resume_conversation_id
            self._resume_conversation_id = None
            logger.info(f"Resuming conversation: {session_id}")
            return session_id, True

        return str(uuid.uuid4()), False

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        """Validate that a session ID is a UUID string."""
        try:
            UUID(session_id)
        except ValueError as exc:
            raise RequestError.invalid_params(
                {"reason": "Invalid session ID format", "sessionId": session_id}
            ) from exc

    @staticmethod
    def _build_load_session_response(
        conversation: BaseConversation,
    ) -> LoadSessionResponse:
        """Build a load-session response using the conversation's current mode."""
        current_mode = get_confirmation_mode_from_conversation(conversation)
        return LoadSessionResponse(modes=get_session_mode_state(current_mode))

    @staticmethod
    def _build_new_session_response(
        session_id: str, conversation: BaseConversation
    ) -> NewSessionResponse:
        """Build a new-session response using the conversation's current mode."""
        current_mode = get_confirmation_mode_from_conversation(conversation)
        return NewSessionResponse(
            session_id=session_id,
            modes=get_session_mode_state(current_mode),
        )

    async def _replay_conversation_events(
        self, session_id: str, events: list[Event], context: str
    ) -> None:
        """Replay stored conversation events to the connected ACP client."""
        if not events:
            return

        logger.info(f"Replaying {len(events)} historic events {context}")
        subscriber = EventSubscriber(session_id, self._conn)
        for event in events:
            await subscriber(event)

    async def _send_agent_text_chunk(self, session_id: str, text: str) -> None:
        """Send a text chunk update to the ACP client."""
        await self._conn.session_update(
            session_id=session_id,
            update=AgentMessageChunk(
                session_update="agent_message_chunk",
                content=TextContentBlock(type="text", text=text),
            ),
        )

    async def _get_slash_command_response(
        self, session_id: str, command: str, argument: str
    ) -> str:
        """Execute a slash command and return its text response."""
        if command == "help":
            return create_help_text()
        if command == "confirm":
            return await self._cmd_confirm(session_id, argument)
        return get_unknown_command_text(command)

    async def _handle_slash_command(
        self, session_id: str, command: str, argument: str
    ) -> PromptResponse:
        """Execute a slash command and send its response back to the client."""
        response_text = await self._get_slash_command_response(
            session_id=session_id,
            command=command,
            argument=argument,
        )
        await self._send_agent_text_chunk(session_id=session_id, text=response_text)
        return PromptResponse(stop_reason="end_turn")

    async def _run_conversation_task(
        self, session_id: str, conversation: BaseConversation
    ) -> None:
        """Run a conversation and track its task for cancellation support."""
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
            self._running_tasks.pop(session_id, None)

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: Any | None = None,  # noqa: ARG002
        client_info: Any | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> InitializeResponse:
        """Initialize the ACP protocol."""
        logger.info(f"Initializing ACP with protocol version: {protocol_version}")

        # Always configure auth method
        auth_methods = [
            AuthMethod(
                description="Authenticate through agent",
                id="oauth",
                name="OAuth with OpenHands Cloud",
                field_meta={"type": "agent"},
            ),
        ]

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
            self._cloud_api_key = self._store.get_api_key()
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

    async def list_sessions(
        self,
        cursor: str | None = None,  # noqa: ARG002
        cwd: str | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> ListSessionsResponse:
        """List available sessions (no-op for now)."""
        logger.info("List sessions requested")
        return ListSessionsResponse(sessions=[])

    async def set_session_mode(
        self,
        mode_id: str,
        session_id: str,
        **_kwargs: Any,
    ) -> SetSessionModeResponse | None:
        """Set session mode by updating confirmation mode."""
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

    async def set_session_model(
        self,
        model_id: str,  # noqa: ARG002
        session_id: str,
        **_kwargs: Any,
    ) -> SetSessionModelResponse | None:
        """Set session model (no-op for now)."""
        logger.info(f"Set session model requested: {session_id}")
        return SetSessionModelResponse()

    async def set_config_option(
        self,
        config_id: str,  # noqa: ARG002
        session_id: str,  # noqa: ARG002
        value: str,  # noqa: ARG002
        **_kwargs: Any,
    ) -> SetSessionConfigOptionResponse | None:
        """Set config option (not supported)."""
        return None

    async def fork_session(
        self,
        cwd: str,  # noqa: ARG002
        session_id: str,  # noqa: ARG002
        mcp_servers: list[Any] | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> ForkSessionResponse:
        """Fork a session (not supported)."""
        raise RequestError.method_not_found("session/fork")

    async def resume_session(
        self,
        cwd: str,  # noqa: ARG002
        session_id: str,  # noqa: ARG002
        mcp_servers: list[Any] | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> ResumeSessionResponse:
        """Resume a session (not supported)."""
        raise RequestError.method_not_found("session/resume")

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Extension method (not supported)."""
        logger.info(f"Extension method '{method}' requested with params: {params}")
        return {"error": "ext_method not supported"}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Extension notification (no-op for now)."""
        logger.info(f"Extension notification '{method}' received with params: {params}")

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

    async def cancel(self, session_id: str, **_kwargs: Any) -> None:
        """Cancel the current operation."""
        logger.info(f"Cancel requested for session: {session_id}")

        try:
            conversation = await self._get_or_create_conversation(session_id=session_id)
            conversation.pause()

            running_task = self._running_tasks.get(session_id)
            if not running_task or running_task.done():
                return

            logger.debug(
                f"Waiting for conversation thread to terminate for session {session_id}"
            )
            await self._wait_for_task_completion(running_task, session_id)

        except RequestError:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel session {session_id}: {e}")
            raise RequestError.internal_error(
                {"reason": "Failed to cancel session", "details": str(e)}
            )

    async def new_session(
        self,
        cwd: str,  # noqa: ARG002
        mcp_servers: list[Any] | None = None,
        working_dir: str | None = None,
        **_kwargs: Any,
    ) -> NewSessionResponse:
        """Create a new conversation session.

        Args:
            cwd: Current working directory (from ACP protocol)
            mcp_servers: ACP MCP servers configuration
            working_dir: Working directory override (for local sessions)

        Returns:
            NewSessionResponse with session ID and modes
        """

        mcp_servers_dict = None
        if mcp_servers:
            mcp_servers_dict = convert_acp_mcp_servers_to_agent_format(mcp_servers)

        session_id, is_resuming = self._get_new_session_context()

        try:
            conversation = await self._get_or_create_conversation(
                session_id=session_id,
                working_dir=working_dir,
                mcp_servers=mcp_servers_dict,
                is_resuming=is_resuming,
            )

            logger.info(f"Created new {self.agent_type} session {session_id}")
            response = self._build_new_session_response(session_id, conversation)

            if is_resuming:
                await self._replay_conversation_events(
                    session_id=session_id,
                    events=conversation.state.events,
                    context=f"for resumed session {session_id}",
                )

            # Schedule available commands notification to be sent after the response.
            # This ensures the client receives the NewSessionResponse (with sessionId)
            # before any session/update notifications, per the ACP spec.
            # Fire-and-forget: notification failure is non-fatal.
            asyncio.create_task(self.send_available_commands(session_id))

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
            logger.error(
                f"Failed to create new {self.agent_type} session: {e}", exc_info=True
            )
            self._cleanup_session(session_id)
            raise RequestError.internal_error(
                {
                    "reason": f"Failed to create new {self.agent_type} session",
                    "details": str(e),
                }
            )

    async def prompt(
        self, prompt: list[Any], session_id: str, **_kwargs: Any
    ) -> PromptResponse:
        """Handle a prompt request with slash command support.

        This method handles:
        - Slash commands (/help, /confirm)
        - Regular prompts with confirmation mode
        """
        try:
            # Get or create conversation (preserves state like pause/confirmation)
            conversation = await self._get_or_create_conversation(session_id=session_id)

            # Convert ACP prompt format to OpenHands message content
            message_content = convert_acp_prompt_to_message_content(prompt)

            if not message_content:
                return PromptResponse(stop_reason="end_turn")

            # Check if this is a slash command (single text block starting with "/")
            text = extract_text_from_message_content(
                message_content, has_exactly_one=True
            )
            slash_cmd = parse_slash_command(text) if text else None
            if slash_cmd:
                command, argument = slash_cmd
                logger.info(f"Executing slash command: /{command} {argument}")
                return await self._handle_slash_command(
                    session_id=session_id,
                    command=command,
                    argument=argument,
                )

            # Send the message with potentially multiple content types
            message = Message(role="user", content=message_content)
            conversation.send_message(message)
            await self._run_conversation_task(
                session_id=session_id,
                conversation=conversation,
            )

            return PromptResponse(stop_reason="end_turn")

        except RequestError:
            raise
        except Exception as e:
            logger.error(f"Error processing prompt: {e}", exc_info=True)
            await self._send_agent_text_chunk(session_id=session_id, text=f"Error: {e}")
            raise RequestError.internal_error(
                {"reason": "Failed to process prompt", "details": str(e)}
            )

    async def load_session(
        self,
        cwd: str,  # noqa: ARG002
        session_id: str,
        mcp_servers: list[Any] | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> LoadSessionResponse | None:
        """Load an existing session and replay conversation history.

        Default implementation for local agent. Cloud agent should override.
        """
        logger.info(f"Loading session: {session_id}")

        try:
            self._validate_session_id(session_id)

            # Get or create conversation (loads from disk if not in cache)
            conversation = await self._get_or_create_conversation(session_id=session_id)

            # Check if there's actually any history to load
            if not conversation.state.events:
                logger.warning(
                    f"Session {session_id} has no history (new or empty session)"
                )
                return self._build_load_session_response(conversation)

            await self._replay_conversation_events(
                session_id=session_id,
                events=conversation.state.events,
                context="from conversation history",
            )

            logger.info(f"Successfully loaded session {session_id}")

            # Send available slash commands to client
            await self.send_available_commands(session_id)

            return self._build_load_session_response(conversation)

        except RequestError:
            raise
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}", exc_info=True)
            raise RequestError.internal_error(
                {"reason": "Failed to load session", "details": str(e)}
            )
