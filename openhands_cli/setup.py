from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

from rich.console import Console

from openhands.sdk import Agent, AgentContext, BaseConversation, Conversation, Plugin, Workspace
from openhands.sdk.context import Skill
from openhands.sdk.event.base import Event
from openhands.sdk.hooks.config import HookConfig
from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
)
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer

# Register tools on import
from openhands_cli.locations import CONVERSATIONS_DIR, PLUGINS_CACHE_DIR, WORK_DIR
from openhands_cli.stores import AgentStore
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


class MissingAgentSpec(Exception):
    """Raised when agent specification is not found or invalid."""

    pass


def load_plugins(plugin_sources: list[str] | None) -> list[Plugin]:
    """Load plugins from local paths or remote URLs.

    Args:
        plugin_sources: List of plugin paths or URLs. Supports:
            - Local paths: ./my-plugin, /absolute/path/to/plugin
            - GitHub URLs: github:owner/repo, github:owner/repo@ref
            - Full URLs: https://github.com/owner/repo

    Returns:
        List of loaded Plugin instances
    """
    if not plugin_sources:
        return []

    console = Console()
    plugins: list[Plugin] = []

    for source in plugin_sources:
        try:
            if source.startswith(("./", "/", "~")) or Path(source).exists():
                # Local path
                expanded_path = Path(source).expanduser().resolve()
                console.print(f"Loading plugin from: {expanded_path}", style="white")
                plugin = Plugin.load(expanded_path)
            else:
                # Remote source (GitHub URL or github: shorthand)
                console.print(f"Fetching plugin from: {source}", style="white")
                plugin_path = Plugin.fetch(
                    source,
                    cache_dir=Path(PLUGINS_CACHE_DIR),
                )
                plugin = Plugin.load(plugin_path)

            plugins.append(plugin)
            console.print(
                f"✓ Loaded plugin: {plugin.name} (v{plugin.version})", style="green"
            )
        except Exception as e:
            console.print(f"✗ Failed to load plugin '{source}': {e}", style="red")
            raise

    return plugins


def merge_plugins_into_agent(
    agent: Agent,
    plugins: list[Plugin],
) -> tuple[Agent, HookConfig | None]:
    """Merge plugin configurations into the agent.

    Args:
        agent: The base agent configuration
        plugins: List of plugins to merge

    Returns:
        Tuple of (updated agent, merged hook config)
    """
    if not plugins:
        return agent, None

    # Collect all skills from plugins
    all_skills: list[Skill] = []
    # Collect all MCP servers from plugins
    all_mcp_servers: dict[str, Any] = {}
    # Collect all hooks from plugins
    merged_hooks: HookConfig | None = None

    for plugin in plugins:
        # Collect skills
        if plugin.skills:
            all_skills.extend(plugin.skills)

        # Collect MCP config
        if plugin.mcp_config:
            mcp_servers = plugin.mcp_config.get("mcpServers", {})
            all_mcp_servers.update(mcp_servers)

        # Merge hooks (later plugins override earlier ones)
        if plugin.hooks:
            if merged_hooks is None:
                merged_hooks = plugin.hooks
            else:
                # Merge hook configs
                merged_hooks = HookConfig(
                    pre_tool_call=merged_hooks.pre_tool_call + plugin.hooks.pre_tool_call
                    if merged_hooks.pre_tool_call and plugin.hooks.pre_tool_call
                    else merged_hooks.pre_tool_call or plugin.hooks.pre_tool_call,
                    post_tool_call=merged_hooks.post_tool_call
                    + plugin.hooks.post_tool_call
                    if merged_hooks.post_tool_call and plugin.hooks.post_tool_call
                    else merged_hooks.post_tool_call or plugin.hooks.post_tool_call,
                )

    # Update agent with skills
    if all_skills:
        if agent.agent_context is not None:
            existing_skills = list(agent.agent_context.skills)
            existing_skills.extend(all_skills)
            agent = agent.model_copy(
                update={
                    "agent_context": agent.agent_context.model_copy(
                        update={"skills": existing_skills}
                    )
                }
            )
        else:
            agent = agent.model_copy(
                update={"agent_context": AgentContext(skills=all_skills)}
            )

    # Update agent with MCP servers
    if all_mcp_servers:
        mcp_config: dict[str, Any] = agent.mcp_config or {}
        existing_servers: dict[str, dict[str, Any]] = mcp_config.get("mcpServers", {})
        existing_servers.update(all_mcp_servers)
        agent = agent.model_copy(
            update={"mcp_config": {"mcpServers": existing_servers}}
        )

    return agent, merged_hooks


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
    plugin_sources: list[str] | None = None,
) -> BaseConversation:
    """
    Setup the conversation with agent.

    Args:
        conversation_id: conversation ID to use. If not provided, a random UUID
            will be generated.
        confirmation_policy: Confirmation policy to use.
        visualizer: Optional visualizer to use. If None, a default will be used
        event_callback: Optional callback function to handle events (e.g., JSON output)
        plugin_sources: Optional list of plugin paths or URLs to load

    Raises:
        MissingAgentSpec: If agent specification is not found or invalid.
    """
    console = Console()
    console.print("Initializing agent...", style="white")

    # Load plugins if specified
    plugins = load_plugins(plugin_sources)

    agent = load_agent_specs(str(conversation_id))

    # Merge plugin configurations into agent
    agent, hook_config = merge_plugins_into_agent(agent, plugins)

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
    if plugins:
        console.print(f"✓ Loaded {len(plugins)} plugin(s)", style="green")

    return conversation
