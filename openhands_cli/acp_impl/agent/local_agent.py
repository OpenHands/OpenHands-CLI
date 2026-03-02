"""OpenHands Local ACP Agent implementation."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from acp import Client, NewSessionResponse, RequestError

from openhands.sdk import (
    BaseConversation,
    Conversation,
    Event,
    LocalConversation,
    Workspace,
)
from openhands.sdk.hooks import HookConfig
from openhands_cli.acp_impl.agent.base_agent import BaseOpenHandsACPAgent
from openhands_cli.acp_impl.agent.util import AgentType
from openhands_cli.acp_impl.confirmation import ConfirmationMode
from openhands_cli.acp_impl.events.event import EventSubscriber
from openhands_cli.acp_impl.events.token_streamer import TokenBasedEventSubscriber
from openhands_cli.acp_impl.slash_commands import (
    apply_confirmation_mode_to_conversation,
)
from openhands_cli.acp_impl.utils import RESOURCE_SKILL
from openhands_cli.locations import MCP_CONFIG_FILE, get_conversations_dir, get_work_dir
from openhands_cli.mcp.mcp_utils import MCPConfigurationError
from openhands_cli.setup import MissingAgentSpec, load_agent_specs


logger = logging.getLogger(__name__)


class LocalOpenHandsACPAgent(BaseOpenHandsACPAgent):
    """OpenHands Local ACP Agent that uses local workspace."""

    def __init__(
        self,
        conn: Client,
        initial_confirmation_mode: ConfirmationMode,
        resume_conversation_id: str | None = None,
        streaming_enabled: bool = False,
    ):
        """Initialize the local ACP agent.

        Args:
            conn: ACP connection for sending notifications
            initial_confirmation_mode: Default confirmation mode for new sessions
            resume_conversation_id: Optional conversation ID to resume
            streaming_enabled: Whether to enable token streaming for LLM outputs
        """
        super().__init__(conn, initial_confirmation_mode, resume_conversation_id)
        self._streaming_enabled: bool = streaming_enabled

        logger.info(
            f"OpenHands Local ACP Agent initialized with confirmation mode: "
            f"{initial_confirmation_mode}, streaming: {streaming_enabled}"
        )

    @property
    def agent_type(self) -> AgentType:
        """Return the agent type."""
        return "local"

    async def _is_authenticated(self) -> bool:
        """Check if agent settings exist or AWS credentials are configured.

        For local agent, authentication is considered complete if:
        1. Agent specs exist (agent_settings.json), OR
        2. AWS credentials are available (for Bedrock users without agent_settings.json)
        """
        try:
            load_agent_specs()
            return True
        except MissingAgentSpec:
            # No agent_settings.json - check if user has AWS credentials for Bedrock
            return self._has_aws_credentials()

    def _has_aws_credentials(self) -> bool:
        """Check if AWS credentials are available for Bedrock authentication.

        This detects users who intend to use AWS Bedrock but haven't yet created
        an agent_settings.json file. We check for:
        1. AWS environment variables (explicit credentials or profile)
        2. AWS credentials/config files (~/.aws/)

        Note: This does NOT validate that credentials are correct - it only
        detects intent to use AWS-based authentication.
        """
        # Check AWS environment variables
        aws_env_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_PROFILE",
            "AWS_DEFAULT_PROFILE",
        ]
        if any(os.environ.get(var) for var in aws_env_vars):
            logger.debug("AWS credentials detected via environment variables")
            return True

        # Check for AWS credentials/config files
        aws_dir = Path.home() / ".aws"
        if (aws_dir / "credentials").exists() or (aws_dir / "config").exists():
            logger.debug("AWS credentials detected via ~/.aws/ files")
            return True

        return False

    def _cleanup_session(self, session_id: str) -> None:
        """Clean up resources for a session (no-op for local agent)."""
        pass

    async def _get_or_create_conversation(
        self,
        session_id: str,
        working_dir: str | None = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
        is_resuming: bool = False,  # noqa: ARG002
    ) -> BaseConversation:
        """Get an active conversation from cache or create/load it."""
        if session_id in self._active_sessions:
            logger.debug(f"Using cached conversation for session {session_id}")
            return self._active_sessions[session_id]

        logger.debug(f"Creating new conversation for session {session_id}")
        conversation = self._setup_conversation(
            session_id=session_id,
            working_dir=working_dir,
            mcp_servers=mcp_servers,
        )

        apply_confirmation_mode_to_conversation(
            conversation, self._initial_confirmation_mode, session_id
        )

        self._active_sessions[session_id] = conversation
        return conversation

    def _setup_conversation(
        self,
        session_id: str,
        working_dir: str | None = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> LocalConversation:
        """Set up a local conversation with event streaming support."""
        try:
            agent = load_agent_specs(
                conversation_id=session_id,
                mcp_servers=mcp_servers,
                skills=[RESOURCE_SKILL],
            )
            streaming_enabled = (
                self._streaming_enabled and not agent.llm.uses_responses_api()
            )

            if streaming_enabled:
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

        if working_dir is None:
            working_dir = get_work_dir()
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
        loop = asyncio.get_event_loop()

        subscriber = EventSubscriber(session_id, self._conn)
        token_subscriber = TokenBasedEventSubscriber(
            session_id=session_id, conn=self._conn, loop=loop
        )

        def sync_callback(event: Event) -> None:
            if streaming_enabled:
                asyncio.run_coroutine_threadsafe(
                    token_subscriber.unstreamed_event_handler(event), loop
                )
            else:
                asyncio.run_coroutine_threadsafe(subscriber(event), loop)

        # Load hooks from ~/.openhands/hooks.json or {working_dir}/.openhands/hooks.json
        hook_config = HookConfig.load(working_dir=str(working_path))
        if not hook_config.is_empty():
            logger.info("Hooks loaded from hooks.json")

        conversation = Conversation(
            agent=agent,
            workspace=workspace,
            persistence_dir=get_conversations_dir(),
            conversation_id=UUID(session_id),
            callbacks=[sync_callback],
            token_callbacks=[token_subscriber.on_token] if streaming_enabled else None,
            visualizer=None,
            hook_config=hook_config,
        )

        subscriber.conversation = conversation
        token_subscriber.conversation = conversation

        return conversation

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[Any],
        working_dir: str | None = None,
        **_kwargs: Any,
    ) -> NewSessionResponse:
        """Create a new conversation session."""
        is_authenticated = await self._is_authenticated()
        if not is_authenticated:
            logger.info("User not authenticated, requiring authentication")
            raise RequestError.auth_required(
                {"reason": "Authentication required to create a session"}
            )

        effective_working_dir = working_dir or cwd or str(Path.cwd())
        logger.info(f"Using working directory: {effective_working_dir}")

        return await super().new_session(
            cwd=cwd,
            mcp_servers=mcp_servers,
            working_dir=effective_working_dir,
            **_kwargs,
        )
