"""Base OpenHands ACP Agent implementation.

This module provides the abstract base class for ACP agents, implementing
common functionality shared between local and cloud agents.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from acp import (
    Agent as ACPAgent,
    Client,
    InitializeResponse,
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

from openhands.sdk import BaseConversation, Message
from openhands_cli.acp_impl.agent.shared_agent_handler import SharedACPAgentHandler
from openhands_cli.acp_impl.agent.util import AgentType, get_session_mode_state
from openhands_cli.acp_impl.confirmation import ConfirmationMode
from openhands_cli.acp_impl.events.event import EventSubscriber
from openhands_cli.acp_impl.runner import run_conversation_with_confirmation
from openhands_cli.acp_impl.slash_commands import (
    create_help_text,
    get_confirmation_mode_from_conversation,
    get_unknown_command_text,
    handle_confirm_argument,
    parse_slash_command,
)
from openhands_cli.acp_impl.utils import convert_acp_prompt_to_message_content
from openhands_cli.utils import extract_text_from_message_content


logger = logging.getLogger(__name__)


class BaseOpenHandsACPAgent(ACPAgent, ABC):
    """Abstract base class for OpenHands ACP agents.

    This class implements common functionality shared between local and cloud agents,
    including:
    - Initialization and protocol handling
    - Slash command processing
    - Prompt handling with confirmation mode
    - Session management delegation to SharedACPAgentHandler

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
    ):
        """Initialize the base ACP agent.

        Args:
            conn: ACP connection for sending notifications
            initial_confirmation_mode: Default confirmation mode for new sessions
            resume_conversation_id: Optional conversation ID to resume
        """
        self._conn = conn
        self._shared_handler = SharedACPAgentHandler(conn)
        self._active_sessions: dict[str, BaseConversation] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._initial_confirmation_mode: ConfirmationMode = initial_confirmation_mode
        self._resume_conversation_id: str | None = resume_conversation_id

        if resume_conversation_id:
            logger.info(f"Will resume conversation: {resume_conversation_id}")

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """Return the agent type ('local' or 'remote')."""
        ...

    @property
    def active_session(self) -> Mapping[str, BaseConversation]:
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
            await self._shared_handler.set_confirmation_mode(self, session_id, new_mode)

        return response_text

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

    async def authenticate(
        self, method_id: str, **_kwargs: Any
    ) -> AuthenticateResponse | None:
        """Authenticate the client (no-op by default, override for cloud)."""
        return await self._shared_handler.authenticate(method_id, **_kwargs)

    async def list_sessions(
        self,
        cursor: str | None = None,
        cwd: str | None = None,
        **_kwargs: Any,
    ) -> ListSessionsResponse:
        """List available sessions (no-op for now)."""
        return await self._shared_handler.list_sessions(cursor, cwd, **_kwargs)

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

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Extension method (not supported)."""
        return await self._shared_handler.ext_method(method, params)

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Extension notification (no-op for now)."""
        await self._shared_handler.ext_notification(method, params)

    async def cancel(self, session_id: str, **_kwargs: Any) -> None:
        """Cancel the current operation."""
        await self._shared_handler.cancel(self, session_id, **_kwargs)

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

                # Execute the slash command
                if command == "help":
                    response_text = create_help_text()
                elif command == "confirm":
                    response_text = await self._cmd_confirm(session_id, argument)
                else:
                    response_text = get_unknown_command_text(command)

                # Send response to client
                await self._conn.session_update(
                    session_id=session_id,
                    update=AgentMessageChunk(
                        session_update="agent_message_chunk",
                        content=TextContentBlock(type="text", text=response_text),
                    ),
                )

                return PromptResponse(stop_reason="end_turn")

            # Send the message with potentially multiple content types
            message = Message(role="user", content=message_content)
            conversation.send_message(message)

            # Run the conversation with confirmation mode via runner function
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
        """Load an existing session and replay conversation history.

        Default implementation for local agent. Cloud agent should override.
        """
        from uuid import UUID

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
            conversation = await self._get_or_create_conversation(session_id=session_id)

            # Check if there's actually any history to load
            if not conversation.state.events:
                logger.warning(
                    f"Session {session_id} has no history (new or empty session)"
                )
                current_mode = get_confirmation_mode_from_conversation(conversation)
                return LoadSessionResponse(modes=get_session_mode_state(current_mode))

            # Stream conversation history to client
            logger.info(
                f"Streaming {len(conversation.state.events)} events from "
                f"conversation history"
            )
            subscriber = EventSubscriber(session_id, self._conn)
            for event in conversation.state.events:
                await subscriber(event)

            logger.info(f"Successfully loaded session {session_id}")

            # Send available slash commands to client
            await self._shared_handler.send_available_commands(session_id)

            # Get current confirmation mode for this session
            current_mode = get_confirmation_mode_from_conversation(conversation)

            return LoadSessionResponse(modes=get_session_mode_state(current_mode))

        except RequestError:
            raise
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}", exc_info=True)
            raise RequestError.internal_error(
                {"reason": "Failed to load session", "details": str(e)}
            )
