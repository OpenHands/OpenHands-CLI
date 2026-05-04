import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from rich.console import Console

from openhands.sdk import Agent, AgentContext, BaseConversation, Conversation, Workspace
from openhands.sdk.context import Skill
from openhands.sdk.event.base import Event
from openhands.sdk.hooks import HookConfig, HookMatcher
from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
)
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands.tools.preset.default import register_builtins_agents

# Register tools on import
from openhands_cli.locations import get_conversations_dir, get_work_dir
from openhands_cli.stores import AgentStore
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


logger = logging.getLogger(__name__)


class MissingAgentSpec(Exception):
    """Raised when agent specification is not found or invalid."""

    pass


def load_agent_specs(
    conversation_id: str | None = None,
    mcp_servers: dict[str, dict[str, Any]] | None = None,
    skills: list[Skill] | None = None,
    *,
    env_overrides_enabled: bool = False,
    critic_disabled: bool = False,
) -> Agent:
    """Load agent specifications.

    Args:
        conversation_id: Optional conversation ID for session tracking
        mcp_servers: Optional dict of MCP servers to augment agent configuration
        skills: Optional list of skills to include in the agent configuration
        env_overrides_enabled: If True, environment variables will override
            stored LLM settings, and agent can be created from env vars if no
            disk config exists.
        critic_disabled: If True, critic functionality will be disabled.

    Returns:
        Configured Agent instance

    Raises:
        MissingAgentSpec: If agent specification is not found or invalid
    """
    agent_store = AgentStore()
    agent = agent_store.load_or_create(
        session_id=conversation_id,
        env_overrides_enabled=env_overrides_enabled,
        critic_disabled=critic_disabled,
    )
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


def strip_stop_hooks(hook_config: HookConfig) -> tuple[HookConfig, list[HookMatcher]]:
    """Strip stop hooks from a HookConfig and return them separately.

    Stop hooks are handled at the CLI level rather than inside the SDK's run loop
    to avoid two issues:
    1. The SDK executes stop hooks while holding the state lock, which blocks pause
    2. A missing hook script exits with code 2 (Python's "file not found"), which
       the SDK interprets as "block the stop" — causing an infinite loop

    Returns:
        Tuple of (hook_config_without_stop, stop_matchers).
    """
    stop_matchers = hook_config.stop
    if not stop_matchers:
        return hook_config, []

    config_without_stop = hook_config.model_copy(update={"stop": []})
    logger.debug(
        "Stripped %d stop hook matcher(s) from HookConfig for CLI-level handling",
        len(stop_matchers),
    )
    return config_without_stop, stop_matchers


def setup_conversation(
    conversation_id: UUID,
    confirmation_policy: ConfirmationPolicyBase,
    visualizer: ConversationVisualizer | None = None,
    event_callback: Callable[[Event], None] | None = None,
    console: Console | None = None,
    *,
    env_overrides_enabled: bool = False,
    critic_disabled: bool = False,
) -> tuple[BaseConversation, list[HookMatcher]]:
    """
    Setup the conversation with agent.

    Args:
        conversation_id: conversation ID to use. If not provided, a random UUID
            will be generated.
        visualizer: Optional visualizer to use. If None, a default will be used
        event_callback: Optional callback function to handle events (e.g., JSON output)
        console: Optional Console for status output. If None, a default Console
            will be created.
        env_overrides_enabled: If True, environment variables will override
            stored LLM settings, and agent can be created from env vars if no
            disk config exists.
        critic_disabled: If True, critic functionality will be disabled.

    Returns:
        Tuple of (conversation, stop_hook_matchers). Stop hooks are stripped from
        the SDK's HookConfig and returned separately for CLI-level handling.

    Raises:
        MissingAgentSpec: If agent specification is not found or invalid.
    """
    if console is None:
        console = Console()
    console.print("Initializing agent...", style="white")

    # Register built-in subagent types (default, explore, bash) so the
    # delegate tool can spawn them.  Uses register_agent_if_absent, so
    # user/project-level definitions still take priority.
    # enable_browser=False because CLI mode doesn't provide browser tools.
    register_builtins_agents(enable_browser=False)

    agent = load_agent_specs(
        str(conversation_id),
        env_overrides_enabled=env_overrides_enabled,
        critic_disabled=critic_disabled,
    )

    # Prepare callbacks list
    callbacks = [event_callback] if event_callback else None

    # Load hooks from ~/.openhands/hooks.json or {working_dir}/.openhands/hooks.json
    hook_config = HookConfig.load(working_dir=get_work_dir())
    if not hook_config.is_empty():
        console.print("✓ Hooks loaded", style="green")

    # Strip stop hooks — they'll be handled at the CLI level to avoid
    # the SDK's state lock blocking pause and exit-code-2 infinite loops.
    hook_config, stop_matchers = strip_stop_hooks(hook_config)

    # Create conversation - agent context is now set in AgentStore.load()
    conversation: BaseConversation = Conversation(
        agent=agent,
        workspace=Workspace(working_dir=get_work_dir()),
        # Conversation will add /<conversation_id> to this path
        persistence_dir=get_conversations_dir(),
        conversation_id=conversation_id,
        visualizer=visualizer,
        callbacks=callbacks,
        hook_config=hook_config,
    )

    conversation.set_security_analyzer(LLMSecurityAnalyzer())
    conversation.set_confirmation_policy(confirmation_policy)

    console.print(f"✓ Agent initialized with model: {agent.llm.model}", style="green")

    return conversation, stop_matchers
