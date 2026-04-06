import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from rich.console import Console

from openhands.sdk import Agent, AgentContext, BaseConversation, Conversation, Workspace
from openhands.sdk.context import Skill
from openhands.sdk.event.base import Event
from openhands.sdk.hooks import HookConfig
from openhands.sdk.hooks.config import HookMatcher
from openhands.sdk.hooks.executor import HookExecutor
from openhands.sdk.hooks.types import HookEvent, HookEventType
from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
)
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer

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


def strip_stop_hooks(
    hook_config: HookConfig,
) -> tuple[HookConfig, list[HookMatcher]]:
    """Strip stop hooks from a HookConfig, returning the modified config and stop hooks.

    Stop hooks are handled at the CLI level (after conversation.run() returns)
    rather than inside the SDK's run loop, because the SDK runs them while holding
    the state lock, which blocks pause() and can cause infinite loops when the
    hook fails with exit code 2 (e.g., Python file-not-found).

    See: https://github.com/OpenHands/OpenHands-CLI/issues/649

    Returns:
        Tuple of (config_without_stop_hooks, stop_hook_matchers).
    """
    stop_hooks = list(hook_config.stop)
    if not stop_hooks:
        return hook_config, []

    # Create a new config without stop hooks
    stripped = HookConfig(
        pre_tool_use=hook_config.pre_tool_use,
        post_tool_use=hook_config.post_tool_use,
        user_prompt_submit=hook_config.user_prompt_submit,
        session_start=hook_config.session_start,
        session_end=hook_config.session_end,
        stop=[],
    )
    return stripped, stop_hooks


def run_stop_hooks(
    stop_matchers: list[HookMatcher],
    working_dir: str,
    session_id: str,
) -> None:
    """Run stop hooks outside the SDK's run loop.

    This executes stop hooks after conversation.run() has returned, without
    holding any locks. Failed hooks are logged but do not prevent the
    conversation from finishing.

    Args:
        stop_matchers: List of HookMatcher objects for stop hooks.
        working_dir: Working directory for hook execution.
        session_id: Session ID passed to hooks.
    """
    executor = HookExecutor(working_dir=working_dir)
    event = HookEvent(
        event_type=HookEventType.STOP,
        session_id=session_id,
        working_dir=working_dir,
        metadata={"reason": "agent_finished"},
    )

    for matcher in stop_matchers:
        for hook_def in matcher.hooks:
            try:
                result = executor.execute(hook_def, event)
                if result.error:
                    logger.warning(f"Stop hook error: {result.error}")
                elif not result.success:
                    logger.warning(
                        f"Stop hook '{hook_def.command}' exited with code "
                        f"{result.exit_code}"
                    )
            except Exception:
                logger.exception(f"Stop hook '{hook_def.command}' failed")


def setup_conversation(
    conversation_id: UUID,
    confirmation_policy: ConfirmationPolicyBase,
    visualizer: ConversationVisualizer | None = None,
    event_callback: Callable[[Event], None] | None = None,
    *,
    env_overrides_enabled: bool = False,
    critic_disabled: bool = False,
) -> tuple[BaseConversation, list[HookMatcher]]:
    """Setup the conversation with agent.

    Stop hooks are stripped from the HookConfig before passing to the SDK and
    returned separately so the caller can run them after conversation.run()
    returns. This prevents the SDK from running them inside its state lock.

    Args:
        conversation_id: conversation ID to use.
        visualizer: Optional visualizer to use. If None, a default will be used
        event_callback: Optional callback function to handle events (e.g., JSON output)
        env_overrides_enabled: If True, environment variables will override
            stored LLM settings, and agent can be created from env vars if no
            disk config exists.
        critic_disabled: If True, critic functionality will be disabled.

    Returns:
        Tuple of (conversation, stop_hook_matchers).

    Raises:
        MissingAgentSpec: If agent specification is not found or invalid.
    """
    console = Console()
    console.print("Initializing agent...", style="white")

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

    # Strip stop hooks from config - they'll be run by the CLI after
    # conversation.run() returns, outside the SDK's state lock.
    hook_config, stop_hooks = strip_stop_hooks(hook_config)

    # Create conversation - agent context is now set in AgentStore.load()
    conversation: BaseConversation = Conversation(
        agent=agent,
        workspace=Workspace(working_dir=get_work_dir()),
        # Conversation will add /<conversation_id> to this path
        persistence_dir=get_conversations_dir(),
        conversation_id=conversation_id,
        visualizer=visualizer,
        callbacks=callbacks,
        hook_config=hook_config if not hook_config.is_empty() else None,
    )

    conversation.set_security_analyzer(LLMSecurityAnalyzer())
    conversation.set_confirmation_policy(confirmation_policy)

    console.print(f"✓ Agent initialized with model: {agent.llm.model}", style="green")

    return conversation, stop_hooks
