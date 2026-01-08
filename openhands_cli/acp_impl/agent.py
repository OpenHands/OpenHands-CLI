"""OpenHands Agent Client Protocol (ACP) server implementation."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from acp import (
    Agent as ACPAgent,
    Client,
    InitializeResponse,
    NewSessionResponse,
    PromptResponse,
    RequestError,
    stdio_streams,
)
from acp.core import AgentSideConnection
from acp.helpers import update_current_mode
from acp.schema import (
    AgentCapabilities,
    AgentMessageChunk,
    AuthenticateResponse,
    AvailableCommandsUpdate,
    Implementation,
    ListSessionsResponse,
    LoadSessionResponse,
    McpCapabilities,
    PromptCapabilities,
    SessionModeState,
    SetSessionModelResponse,
    SetSessionModeResponse,
    TextContentBlock,
)

from openhands.sdk import (
    Conversation,
    Event,
    LocalConversation,
    Message,
    Workspace,
)
from openhands_cli import __version__
from openhands_cli.acp_impl.confirmation import (
    ConfirmationMode,
    get_available_modes,
)
from openhands_cli.acp_impl.events.event import EventSubscriber
from openhands_cli.acp_impl.events.token_streamer import TokenBasedEventSubscriber
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
    RESOURCE_SKILL,
    convert_acp_mcp_servers_to_agent_format,
    convert_acp_prompt_to_message_content,
)
from openhands_cli.locations import CONVERSATIONS_DIR, MCP_CONFIG_FILE, WORK_DIR
from openhands_cli.mcp.mcp_utils import MCPConfigurationError
from openhands_cli.setup import MissingAgentSpec, load_agent_specs
from openhands_cli.utils import extract_text_from_message_content


logger = logging.getLogger(__name__)


def get_session_mode_state(current_mode: ConfirmationMode) -> SessionModeState:
    """Get the session mode state for a given confirmation mode.

    Args:
        current_mode: The current confirmation mode

    Returns:
        SessionModeState with available modes and current mode
    """
    return SessionModeState(
        current_mode_id=current_mode,
        available_modes=get_available_modes(),
    )


class OpenHandsACPAgent(ACPAgent):
    """OpenHands Agent Client Protocol implementation."""

    def __init__(
        self,
        conn: Client,
        initial_confirmation_mode: ConfirmationMode,
        resume_conversation_id: str | None = None,
        streaming_enabled: bool = False,
    ):
        """Initialize the OpenHands ACP agent.

        Args:
            conn: ACP connection for sending notifications
            initial_confirmation_mode: Default confirmation mode for new sessions
            resume_conversation_id: Optional conversation ID to resume when a new
                session is created (used with --resume flag)
            streaming_enabled: Whether to enable token streaming for LLM outputs
        """
        self._conn = conn
        # Cache of active conversations to preserve state (pause, confirmation, etc.)
        # across multiple operations on the same session
        self._active_sessions: dict[str, LocalConversation] = {}
        # Track running tasks for each session to ensure proper cleanup on cancel
        self._running_tasks: dict[str, asyncio.Task] = {}
        # Default confirmation mode for new sessions
        self._initial_confirmation_mode: ConfirmationMode = initial_confirmation_mode
        # Conversation ID to resume (from --resume flag)
        self._resume_conversation_id: str | None = resume_conversation_id
        # Whether token streaming is enabled (from --streaming flag)
        self._streaming_enabled: bool = streaming_enabled
        logger.info(
            f"OpenHands ACP Agent initialized with confirmation mode: "
            f"{initial_confirmation_mode}, streaming: {streaming_enabled}"
        )
        if resume_conversation_id:
            logger.info(f"Will resume conversation: {resume_conversation_id}")

    async def _cmd_confirm(self, session_id: str, argument: str) -> str:
        """Handle /confirm command.

        Args:
            session_id: The session ID
            argument: Command argument (always-ask|always-approve|llm-approve)

        Returns:
            Status message
        """
        # Get current mode from conversation if it exists
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

    async def _send_available_commands(self, session_id: str) -> None:
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

    def on_connect(self, conn: Client) -> None:
        pass

    def _get_or_create_conversation(
        self,
        session_id: str,
        working_dir: str | None = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> LocalConversation:
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

        # Initialize confirmation mode to the configured default
        # Set the confirmation policy on the conversation
        apply_confirmation_mode_to_conversation(
            conversation, self._initial_confirmation_mode, session_id
        )

        # Cache it for future operations
        self._active_sessions[session_id] = conversation
        return conversation

    def _setup_acp_conversation(
        self,
        session_id: str,
        working_dir: str | None = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> LocalConversation:
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
            RequestError: If MCP configuration is invalid
        """
        # Load agent specs (same as setup_conversation)
        try:
            agent = load_agent_specs(
                conversation_id=session_id,
                mcp_servers=mcp_servers,
                skills=[RESOURCE_SKILL],
            )
            # Streaming is enabled only if:
            # 1. The --streaming flag was passed (self._streaming_enabled)
            # 2. The LLM doesn't use responses API (which doesn't support streaming)
            streaming_enabled = (
                self._streaming_enabled and not agent.llm.uses_responses_api()
            )

            if streaming_enabled:
                # Enable streaming for llm
                agent = agent.model_copy(
                    update={"llm": agent.llm.model_copy(update={"stream": True})}
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

        # Get the current event loop for the callback
        loop = asyncio.get_event_loop()

        # Create event subscriber for streaming updates (ACP-specific)
        # Pass streaming_enabled=True to indicate token streaming is active
        subscriber = EventSubscriber(session_id, self._conn)
        token_subscriber = TokenBasedEventSubscriber(
            session_id=session_id, conn=self._conn, loop=loop
        )

        def sync_callback(event: Event) -> None:
            """Synchronous wrapper that schedules async event handling."""
            if streaming_enabled:
                asyncio.run_coroutine_threadsafe(
                    token_subscriber.unstreamed_event_handler(event), loop
                )
            else:
                asyncio.run_coroutine_threadsafe(subscriber(event), loop)

        # Create conversation with persistence support and token streaming
        # The SDK automatically loads from disk if conversation_id exists
        conversation = Conversation(
            agent=agent,
            workspace=workspace,
            persistence_dir=CONVERSATIONS_DIR,
            conversation_id=UUID(session_id),
            callbacks=[sync_callback],
            token_callbacks=[token_subscriber.on_token]
            if streaming_enabled
            else None,  # Enable token streaming only when --streaming flag is used
            visualizer=None,  # No visualizer needed for ACP
        )

        # Set conversation reference in subscriber for metrics access
        subscriber.conversation = conversation
        token_subscriber.conversation = conversation

        # # Set up security analyzer (same as setup_conversation with confirmation mode)
        # conversation.set_security_analyzer(LLMSecurityAnalyzer())
        # conversation.set_confirmation_policy(AlwaysConfirm())
        # TODO: implement later

        return conversation

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

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[Any],
        **_kwargs: Any,
    ) -> NewSessionResponse:
        """Create a new conversation session.

        If --resume was used when starting the ACP server, the first new_session
        call will use the specified conversation ID instead of generating a new one.
        When resuming, historic events are replayed to the client.
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

            # Validate working directory
            working_dir = cwd or str(Path.cwd())
            logger.info(f"Using working directory: {working_dir}")

            # Create conversation and cache it for future operations
            # This reuses the same pattern as openhands --resume
            conversation = self._get_or_create_conversation(
                session_id=session_id,
                working_dir=working_dir,
                mcp_servers=mcp_servers_dict,
            )

            logger.info(f"Created new session {session_id}")

            # Send available slash commands to client
            await self._send_available_commands(session_id)

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
            # Re-raise RequestError as-is
            raise
        except Exception as e:
            logger.error(f"Failed to create new session: {e}", exc_info=True)
            raise RequestError.internal_error(
                {"reason": "Failed to create new session", "details": str(e)}
            )

    async def prompt(
        self, prompt: list[Any], session_id: str, **_kwargs: Any
    ) -> PromptResponse:
        """Handle a prompt request."""
        try:
            # Get or create conversation (preserves state like pause/confirmation)
            conversation = self._get_or_create_conversation(session_id=session_id)

            # Convert ACP prompt format to OpenHands message content
            message_content = convert_acp_prompt_to_message_content(prompt)

            if not message_content:
                return PromptResponse(stop_reason="end_turn")

            # Check if this is a slash command (single text block starting with "/")
            # multiple blocks not valid slash commands -> has_exactly_one = True
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
            # Re-raise RequestError as-is
            raise
        except Exception as e:
            logger.error(f"Error processing prompt: {e}", exc_info=True)
            # Send error notification to client
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
            conversation = self._get_or_create_conversation(session_id=session_id)
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

    async def load_session(
        self,
        cwd: str,  # noqa: ARG002
        mcp_servers: list[Any],  # noqa: ARG002
        session_id: str,
        **_kwargs: Any,
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
                # Get current confirmation mode for this session
                current_mode = get_confirmation_mode_from_conversation(conversation)
                return LoadSessionResponse(modes=get_session_mode_state(current_mode))

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

            # Send available slash commands to client
            await self._send_available_commands(session_id)

            # Get current confirmation mode for this session
            current_mode = get_confirmation_mode_from_conversation(conversation)

            # Return response with modes
            return LoadSessionResponse(modes=get_session_mode_state(current_mode))

        except RequestError:
            # Re-raise RequestError as-is
            raise
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}", exc_info=True)
            raise RequestError.internal_error(
                {"reason": "Failed to load session", "details": str(e)}
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


async def run_acp_server(
    initial_confirmation_mode: ConfirmationMode = "always-ask",
    resume_conversation_id: str | None = None,
    streaming_enabled: bool = False,
) -> None:
    """Run the OpenHands ACP server.

    Args:
        initial_confirmation_mode: Default confirmation mode for new sessions
        resume_conversation_id: Optional conversation ID to resume when a new
            session is created
        streaming_enabled: Whether to enable token streaming for LLM outputs
    """
    logger.info(
        f"Starting OpenHands ACP server with confirmation mode: "
        f"{initial_confirmation_mode}, streaming: {streaming_enabled}..."
    )
    if resume_conversation_id:
        logger.info(f"Will resume conversation: {resume_conversation_id}")

    reader, writer = await stdio_streams()

    def create_agent(conn: Client) -> OpenHandsACPAgent:
        return OpenHandsACPAgent(
            conn, initial_confirmation_mode, resume_conversation_id, streaming_enabled
        )

    AgentSideConnection(create_agent, writer, reader)

    # Keep the server running
    await asyncio.Event().wait()
