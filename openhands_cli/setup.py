import json
from pathlib import Path
from typing import Any
from uuid import UUID

from prompt_toolkit import HTML, print_formatted_text

from openhands.sdk import Agent, AgentContext, BaseConversation, Conversation, Workspace
from openhands.sdk.context import Skill
from openhands.sdk.conversation.persistence_const import BASE_STATE
from openhands.sdk.io import LocalFileStore
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

    # Check if we're resuming an existing conversation by looking for persisted state
    conv_state_dir = Path(CONVERSATIONS_DIR) / conversation_id.hex
    is_resuming = False

    if conv_state_dir.exists():
        try:
            file_store = LocalFileStore(str(conv_state_dir))
            base_text = file_store.read(BASE_STATE)
            if base_text:
                is_resuming = True
                # Load persisted state to get the original agent's LLM settings
                state_data = json.loads(base_text)
                persisted_agent_data = state_data.get("agent", {})

                # Create agent with persisted LLM settings but current
                # runtime values. This allows resuming with the original
                # model/settings while updating runtime-specific fields
                # like API keys and metadata
                if persisted_agent_data:
                    persisted_agent = Agent.model_validate(persisted_agent_data)

                    # Save reference to current agent from AgentStore
                    current_agent = agent

                    # Update only fields allowed to change
                    # (from OVERRIDE_ON_SERIALIZE)
                    llm_updates = {}
                    for field in persisted_agent.llm.OVERRIDE_ON_SERIALIZE:
                        llm_updates[field] = getattr(current_agent.llm, field)

                    # Use persisted agent with updated runtime secrets
                    agent = persisted_agent.model_copy(
                        update={
                            "llm": persisted_agent.llm.model_copy(update=llm_updates),
                            # Keep current tools, context, and MCP config
                            "tools": current_agent.tools,
                            "agent_context": current_agent.agent_context,
                            "mcp_config": current_agent.mcp_config,
                        }
                    )

                    # Also update condenser LLM if present
                    if persisted_agent.condenser and hasattr(
                        persisted_agent.condenser, "llm"
                    ):
                        # Get runtime secrets from current agent's condenser
                        condenser_llm_updates = {}
                        current_condenser = (
                            current_agent.condenser if current_agent.condenser else None
                        )
                        if current_condenser and hasattr(current_condenser, "llm"):
                            persisted_condenser_llm = getattr(
                                persisted_agent.condenser, "llm"
                            )
                            current_condenser_llm = getattr(current_condenser, "llm")
                            for field in persisted_condenser_llm.OVERRIDE_ON_SERIALIZE:
                                condenser_llm_updates[field] = getattr(
                                    current_condenser_llm,
                                    field,
                                )
                            # Apply updates to persisted condenser LLM
                            agent = agent.model_copy(
                                update={
                                    "condenser": persisted_agent.condenser.model_copy(
                                        update={
                                            "llm": persisted_condenser_llm.model_copy(
                                                update=condenser_llm_updates
                                            )
                                        }
                                    )
                                }
                            )
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            # If we can't read the state, just proceed with the current agent
            pass

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

    if is_resuming:
        print_formatted_text(
            HTML(f"<green>✓ Resumed conversation with model: {agent.llm.model}</green>")
        )
    else:
        print_formatted_text(
            HTML(f"<green>✓ Agent initialized with model: {agent.llm.model}</green>")
        )
    return conversation
