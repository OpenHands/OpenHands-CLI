from typing import Any
from uuid import UUID

from prompt_toolkit import HTML, print_formatted_text

from openhands.sdk import Agent, AgentContext, BaseConversation, Conversation, Workspace
from openhands.sdk.context import Skill
from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
)
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer

# Register tools on import
from openhands.tools.file_editor import FileEditorTool  # noqa: F401
from openhands.tools.task_tracker import TaskTrackerTool  # noqa: F401
from openhands.tools.terminal import TerminalTool  # noqa: F401
from openhands_cli.locations import CONVERSATIONS_DIR, WORK_DIR
from openhands_cli.refactor.widgets.richlog_visualizer import ConversationVisualizer
from openhands_cli.tui.settings.settings_screen import SettingsScreen
from openhands_cli.tui.settings.store import AgentStore
from openhands_cli.tui.visualizer import CLIVisualizer


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
            "Agent specification not found. Please configure your agent settings."
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


def verify_agent_exists_or_setup_agent() -> Agent:
    """Verify agent specs exists by attempting to load it."""
    settings_screen = SettingsScreen()
    try:
        agent = load_agent_specs()
        return agent
    except MissingAgentSpec:
        # For first-time users, show the full settings flow with choice
        # between basic/advanced
        settings_screen.configure_settings(first_time=True)

    # Try once again after settings setup attempt
    return load_agent_specs()


def setup_conversation(
    conversation_id: UUID,
    confirmation_policy: ConfirmationPolicyBase,
    visualizer: ConversationVisualizer | None = None,
) -> BaseConversation:
    """
    Setup the conversation with agent.

    Args:
        conversation_id: conversation ID to use. If not provided, a random UUID
            will be generated.
        confirmation_policy: Confirmation policy to use.
        visualizer: Optional visualizer to use. If None, defaults to CLIVisualizer

    Raises:
        MissingAgentSpec: If agent specification is not found or invalid.
    """

    print_formatted_text(HTML("<white>Initializing agent...</white>"))

    agent = load_agent_specs(str(conversation_id))

    # Create conversation - agent context is now set in AgentStore.load()
    conversation: BaseConversation = Conversation(
        agent=agent,
        workspace=Workspace(working_dir=WORK_DIR),
        # Conversation will add /<conversation_id> to this path
        persistence_dir=CONVERSATIONS_DIR,
        conversation_id=conversation_id,
        visualizer=visualizer if visualizer is not None else CLIVisualizer,
    )

    conversation.set_security_analyzer(LLMSecurityAnalyzer())
    conversation.set_confirmation_policy(confirmation_policy)

    print_formatted_text(
        HTML(f"<green>✓ Agent initialized with model: {agent.llm.model}</green>")
    )
    return conversation
