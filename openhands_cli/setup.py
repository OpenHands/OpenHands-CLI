from collections.abc import Callable
from typing import Any
from uuid import UUID

from rich.console import Console

from openhands.sdk import (
    Agent,
    AgentContext,
    BaseConversation,
    Conversation,
    RemoteConversation,
    Workspace,
)
from openhands.sdk.context import Skill
from openhands.sdk.event.base import Event
from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
)
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer

# Register tools on import
from openhands.tools.file_editor import FileEditorTool  # noqa: F401
from openhands.tools.task_tracker import TaskTrackerTool  # noqa: F401
from openhands.tools.terminal import TerminalTool  # noqa: F401
from openhands_cli.locations import CONVERSATIONS_DIR, WORK_DIR
from openhands_cli.stores import AgentStore
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


class MissingAgentSpec(Exception):
    """Raised when agent specification is not found or invalid."""

    pass


def load_agent_specs(
    conversation_id: str | None = None,
    mcp_servers: dict[str, dict[str, Any]] | None = None,
    skills: list[Skill] | None = None,
) -> Agent:
    """Load agent specifications.

    Args:
        conversation_id: Optional conversation ID for session tracking
        mcp_servers: Optional dict of MCP servers to augment agent configuration
        skills: Optional list of skills to include in the agent configuration

    Returns:
        Configured Agent instance

    Raises:
        MissingAgentSpec: If agent specification is not found or invalid
    """
    agent_store = AgentStore()
    agent = agent_store.load(session_id=conversation_id)
    if not agent:
        raise MissingAgentSpec(
            "Agent specification not found. Please configure your settings."
        )

    # If MCP servers are provided, augment the agent's MCP configuration
    if mcp_servers:
        # Merge with existing MCP configuration (provided servers take precedence)
        mcp_config: dict[str, Any] = agent.mcp_config or {}
        existing_servers: dict[str, dict[str, Any]] = mcp_config.get("mcpServers", {})
        existing_servers.update(mcp_servers)
        agent = agent.model_copy(
            update={"mcp_config": {"mcpServers": existing_servers}}
        )

    if skills:
        if agent.agent_context is not None:
            existing_skills = agent.agent_context.skills
            existing_skills.extend(skills)
            agent = agent.model_copy(
                update={
                    "agent_context": agent.agent_context.model_copy(
                        update={"skills": existing_skills}
                    )
                }
            )
        else:
            agent = agent.model_copy(
                update={"agent_context": AgentContext(skills=skills)}
            )

    return agent


def setup_conversation(
    conversation_id: UUID,
    confirmation_policy: ConfirmationPolicyBase,
    visualizer: ConversationVisualizer | None = None,
    event_callback: Callable[[Event], None] | None = None,
    cloud: bool = False,
    server_url: str | None = None,
    sandbox_id: str | None = None,
) -> BaseConversation:
    """
    Setup the conversation with agent.

    Args:
        conversation_id: conversation ID to use. If not provided, a random UUID
            will be generated.
        confirmation_policy: Confirmation policy to use.
        visualizer: Optional visualizer to use. If None, a default will be used
        event_callback: Optional callback function to handle events (e.g., JSON output)
        cloud: If True, use OpenHands Cloud for remote execution.
        server_url: The OpenHands Cloud server URL (used when cloud=True).
        sandbox_id: Optional sandbox ID to reclaim an existing sandbox (cloud mode).

    Raises:
        MissingAgentSpec: If agent specification is not found or invalid.
    """
    console = Console()

    if cloud:
        return setup_cloud_conversation(
            conversation_id=conversation_id,
            confirmation_policy=confirmation_policy,
            visualizer=visualizer,
            event_callback=event_callback,
            server_url=server_url,
            sandbox_id=sandbox_id,
        )

    console.print("Initializing agent...", style="white")

    agent = load_agent_specs(str(conversation_id))

    # Prepare callbacks list
    callbacks = [event_callback] if event_callback else None

    # Create conversation - agent context is now set in AgentStore.load()
    conversation: BaseConversation = Conversation(
        agent=agent,
        workspace=Workspace(working_dir=WORK_DIR),
        # Conversation will add /<conversation_id> to this path
        persistence_dir=CONVERSATIONS_DIR,
        conversation_id=conversation_id,
        visualizer=visualizer,
        callbacks=callbacks,
    )

    conversation.set_security_analyzer(LLMSecurityAnalyzer())
    conversation.set_confirmation_policy(confirmation_policy)

    console.print(f"✓ Agent initialized with model: {agent.llm.model}", style="green")
    return conversation


def setup_cloud_conversation(
    conversation_id: UUID,
    confirmation_policy: ConfirmationPolicyBase,
    visualizer: ConversationVisualizer | None = None,
    event_callback: Callable[[Event], None] | None = None,
    server_url: str | None = None,
    sandbox_id: str | None = None,
) -> BaseConversation:
    """
    Setup a cloud conversation using OpenHands Cloud.

    Args:
        conversation_id: conversation ID to use.
        confirmation_policy: Confirmation policy to use.
        visualizer: Optional visualizer to use.
        event_callback: Optional callback function to handle events.
        server_url: The OpenHands Cloud server URL.
        sandbox_id: Optional sandbox ID to reclaim an existing sandbox.

    Raises:
        ValueError: If API key is not available.
    """
    import os

    from openhands.workspace import OpenHandsCloudWorkspace
    from openhands_cli.auth.token_storage import TokenStorage
    from openhands_cli.cloud.conversation import CloudConversationError

    # Get API key from token storage
    store = TokenStorage()
    if not store.has_api_key():
        raise CloudConversationError(
            "Not logged in to OpenHands Cloud. Run 'openhands login' first."
        )
    api_key = store.get_api_key()
    if not api_key:
        raise CloudConversationError(
            "Invalid API key stored. Run 'openhands login' to re-authenticate."
        )

    # Use default server URL if not provided
    if not server_url:
        server_url = os.getenv("OPENHANDS_CLOUD_URL", "https://app.all-hands.dev")

    # Load agent specs for the conversation
    agent = load_agent_specs(str(conversation_id))

    # Create cloud workspace with optional sandbox_id to reclaim existing sandbox
    workspace = OpenHandsCloudWorkspace(
        cloud_api_url=server_url,
        cloud_api_key=api_key,
        sandbox_id=sandbox_id,
        keep_alive=True,
    )

    # Prepare callbacks list
    callbacks = [event_callback] if event_callback else None

    # Create RemoteConversation
    # Note: RemoteConversation gets its HTTP client from workspace.client
    # which is configured with the correct host and api_key after sandbox starts
    conversation: BaseConversation = RemoteConversation(
        agent=agent,
        workspace=workspace,
        conversation_id=conversation_id,
        visualizer=visualizer,
        callbacks=callbacks,
    )

    conversation.set_security_analyzer(LLMSecurityAnalyzer())
    conversation.set_confirmation_policy(confirmation_policy)
    return conversation
