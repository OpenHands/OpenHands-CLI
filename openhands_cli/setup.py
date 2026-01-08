from collections.abc import Callable
from typing import Any
from uuid import UUID

from rich.console import Console

from openhands.sdk import Agent, AgentContext, BaseConversation, Conversation, Workspace
from openhands.sdk.context import Skill
from openhands.sdk.event.base import Event
from openhands.sdk.hooks import HookConfig
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


def load_hook_config(working_dir: str | None = None) -> HookConfig | None:
    """Load hook configuration from the working directory.

    Searches for hooks.json in:
    1. <working_dir>/.openhands/hooks.json
    2. ~/.openhands/hooks.json

    Args:
        working_dir: Working directory to search for hooks.json.
            Defaults to WORK_DIR if not provided.

    Returns:
        HookConfig if found, None otherwise.
    """
    search_dir = working_dir or str(WORK_DIR)
    config = HookConfig.load(working_dir=search_dir)

    # Return None if no hooks are configured (empty config)
    if not config.hooks:
        return None

    return config


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
    hook_config: HookConfig | None = None,
) -> BaseConversation:
    """
    Setup the conversation with agent.

    Args:
        conversation_id: conversation ID to use. If not provided, a random UUID
            will be generated.
        confirmation_policy: Confirmation policy to use.
        visualizer: Optional visualizer to use. If None, a default will be used
        event_callback: Optional callback function to handle events (e.g., JSON output)
        hook_config: Optional hook configuration for event-driven automation.
            If None, hooks will be auto-discovered from .openhands/hooks.json.

    Raises:
        MissingAgentSpec: If agent specification is not found or invalid.
    """
    console = Console()
    console.print("Initializing agent...", style="white")

    agent = load_agent_specs(str(conversation_id))

    # Load hook configuration if not provided
    # Auto-discover from .openhands/hooks.json in working directory or home
    if hook_config is None:
        hook_config = load_hook_config(str(WORK_DIR))

    if hook_config is not None:
        console.print("✓ Hooks configuration loaded", style="dim")

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
        hook_config=hook_config,
    )

    conversation.set_security_analyzer(LLMSecurityAnalyzer())
    conversation.set_confirmation_policy(confirmation_policy)

    console.print(f"✓ Agent initialized with model: {agent.llm.model}", style="green")
    return conversation
