# openhands_cli/stores/agent_store.py
from __future__ import annotations

import json
import os
import re
from typing import Any

from prompt_toolkit import HTML, print_formatted_text
from pydantic import BaseModel, SecretStr
from rich.console import Console

from openhands.sdk import (
    LLM,
    Agent,
    AgentContext,
    LLMSummarizingCondenser,
    LocalFileStore,
)
from openhands.sdk.context import load_project_skills
from openhands.sdk.conversation.persistence_const import BASE_STATE
from openhands.sdk.critic.base import CriticBase
from openhands.sdk.critic.impl.api import APIBasedCritic
from openhands.sdk.tool import Tool
from openhands_cli.locations import (
    AGENT_SETTINGS_PATH,
    CONVERSATIONS_DIR,
    PERSISTENCE_DIR,
    WORK_DIR,
)
from openhands_cli.mcp.mcp_utils import list_enabled_servers
from openhands_cli.stores.cli_settings import CliSettings
from openhands_cli.utils import (
    get_default_cli_agent,
    get_default_cli_tools,
    get_llm_metadata,
    get_os_description,
    should_set_litellm_extra_body,
)


def get_persisted_conversation_tools(conversation_id: str) -> list[Tool] | None:
    """Get tools from a persisted conversation's base_state.json.

    When resuming a conversation, we should use the tools that were available
    when the conversation was created, not the current default tools. This
    ensures consistency and prevents issues with tools that weren't available
    in the original conversation (e.g., delegate tool).

    Args:
        conversation_id: The conversation ID to look up

    Returns:
        List of Tool objects from the persisted conversation, or None if
        the conversation doesn't exist or can't be read
    """
    conversation_dir = os.path.join(CONVERSATIONS_DIR, conversation_id)
    base_state_path = os.path.join(conversation_dir, BASE_STATE)

    if not os.path.exists(base_state_path):
        return None

    try:
        with open(base_state_path) as f:
            state_data = json.load(f)

        # Extract tools from the persisted agent
        agent_data = state_data.get("agent", {})
        tools_data = agent_data.get("tools", [])

        if not tools_data:
            return None

        # Convert tool data to Tool objects
        return [Tool.model_validate(tool) for tool in tools_data]
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def get_default_critic(llm: LLM, *, enable_critic: bool = True) -> CriticBase | None:
    """Auto-configure critic for All-Hands LLM proxy.

    When the LLM base_url matches `llm-proxy.*.all-hands.dev`, returns an
    APIBasedCritic configured with:
    - server_url: {base_url}/vllm
    - api_key: same as LLM
    - model_name: "critic"

    Returns None if base_url doesn't match, api_key is not set, or enable_critic
    is False.

    Args:
        llm: The LLM configuration
        enable_critic: Whether critic feature is enabled (from settings)
    """
    # Check if critic is enabled in settings
    if not enable_critic:
        return None

    base_url = llm.base_url
    api_key = llm.api_key
    if base_url is None or api_key is None:
        return None

    # Match: llm-proxy.{env}.all-hands.dev (e.g., staging, prod, eval, app)
    pattern = r"^https?://llm-proxy\.[^./]+\.all-hands\.dev"
    if not re.match(pattern, base_url):
        return None

    try:
        return APIBasedCritic(
            server_url=f"{base_url.rstrip('/')}/vllm",
            api_key=api_key,
            model_name="critic",
        )
    except Exception:
        # If critic creation fails, silently return None
        # This allows the CLI to continue working without critic
        return None


DEFAULT_LLM_BASE_URL = "https://llm-proxy.app.all-hands.dev/"

# Environment variable names for LLM configuration
ENV_LLM_API_KEY = "LLM_API_KEY"
ENV_LLM_BASE_URL = "LLM_BASE_URL"
ENV_LLM_MODEL = "LLM_MODEL"


class MissingEnvironmentVariablesError(Exception):
    """Raised when required environment variables are missing for headless mode.

    This exception is raised when --override-with-envs is enabled but required
    environment variables (LLM_API_KEY and LLM_MODEL) are not set.
    """

    def __init__(self, missing_vars: list[str]) -> None:
        self.missing_vars = missing_vars
        vars_str = ", ".join(missing_vars)
        super().__init__(
            f"Missing required environment variable(s): {vars_str}\n"
            f"When using --override-with-envs, you must set:\n"
            f"  - {ENV_LLM_API_KEY}: Your LLM API key\n"
            f"  - {ENV_LLM_MODEL}: The model to use (e.g., claude-sonnet-4-5-20250929)"
        )


def check_and_warn_env_vars() -> None:
    """Check for LLM environment variables and warn if they are set but not used.

    This function should be called when env overrides are disabled to inform
    users that their environment variables are being ignored.
    """
    env_vars_set = []
    if os.environ.get(ENV_LLM_API_KEY):
        env_vars_set.append(ENV_LLM_API_KEY)
    if os.environ.get(ENV_LLM_BASE_URL):
        env_vars_set.append(ENV_LLM_BASE_URL)
    if os.environ.get(ENV_LLM_MODEL):
        env_vars_set.append(ENV_LLM_MODEL)

    if env_vars_set:
        console = Console(stderr=True)
        vars_str = ", ".join(env_vars_set)
        console.print(
            f"[yellow]Warning:[/yellow] Environment variable(s) {vars_str} detected "
            "but will be ignored.\n"
            "Use [bold]--override-with-envs[/bold] flag to apply them.",
            highlight=False,
        )


class LLMEnvOverrides(BaseModel):
    """LLM configuration overrides from environment variables.

    All fields are optional - only override the ones which are provided.
    Environment variables take precedence over stored settings and are
    NOT persisted to disk (temporary override only).

    Use the `from_env()` class method to load values from environment
    variables when env overrides are enabled.
    """

    api_key: SecretStr | None = None
    base_url: str | None = None
    model: str | None = None

    @classmethod
    def from_env(cls, enabled: bool = False) -> LLMEnvOverrides:
        """Create LLMEnvOverrides from environment variables.

        Args:
            enabled: If True, load values from environment variables.
                     If False, return empty overrides.

        Returns:
            LLMEnvOverrides instance with values from env vars (if enabled)
            or empty overrides (if disabled).
        """
        if not enabled:
            return cls()

        result: dict[str, Any] = {}

        api_key_str = os.environ.get(ENV_LLM_API_KEY) or None
        if api_key_str:
            result["api_key"] = SecretStr(api_key_str)

        base_url = os.environ.get(ENV_LLM_BASE_URL) or None
        if base_url:
            result["base_url"] = base_url

        model = os.environ.get(ENV_LLM_MODEL) or None
        if model:
            result["model"] = model

        return cls(**result)

    def require_for_headless(self) -> None:
        missing: list[str] = []
        if self.api_key is None:
            missing.append(ENV_LLM_API_KEY)
        if self.model is None:
            missing.append(ENV_LLM_MODEL)
        if missing:
            raise MissingEnvironmentVariablesError(missing)

    def has_overrides(self) -> bool:
        """Check if any overrides are set."""
        return any([self.api_key, self.base_url, self.model])


def apply_llm_overrides(llm: LLM, overrides: LLMEnvOverrides) -> LLM:
    """Apply environment variable overrides to an LLM instance.

    Args:
        llm: The LLM instance to update
        overrides: LLMEnvOverrides instance from get_env_llm_overrides()

    Returns:
        Updated LLM instance with overrides applied
    """
    if not overrides.has_overrides():
        return llm

    return llm.model_copy(update=overrides.model_dump(exclude_none=True))


class AgentStore:
    """Single source of truth for persisting/retrieving AgentSpec."""

    def __init__(self) -> None:
        self.file_store = LocalFileStore(root=PERSISTENCE_DIR)

    def load_from_disk(self) -> Agent | None:
        """Load an agent configuration from disk storage.

        This method only loads the persisted agent configuration. It does not
        apply runtime configuration or create agents from environment variables.

        Returns:
            Raw Agent instance from disk, or None if no configuration exists
            or the file is corrupted.
        """
        try:
            str_spec = self.file_store.read(AGENT_SETTINGS_PATH)
            # Respects user choices persisted in agent_settings.json on disk.
            return Agent.model_validate_json(str_spec)
        except FileNotFoundError:
            return None
        except Exception:
            print_formatted_text(
                HTML("\n<red>Agent configuration file is corrupted!</red>")
            )
            return None

    def _ensure_agent(self, agent: Agent | None, overrides: LLMEnvOverrides) -> Agent:
        if agent is not None:
            return agent

        # In env override mode, require enough info to create an agent.
        overrides.require_for_headless()
        assert overrides.api_key is not None
        assert overrides.model is not None

        llm = LLM(
            model=overrides.model,
            api_key=overrides.api_key.get_secret_value(),
            base_url=overrides.base_url,
            usage_id="agent",
        )
        return get_default_cli_agent(llm)

    def _apply_env_overrides(self, agent: Agent, overrides: LLMEnvOverrides) -> Agent:
        if not overrides.has_overrides():
            return agent

        updated_llm = apply_llm_overrides(agent.llm, overrides)

        condenser = None
        if agent.condenser and isinstance(agent.condenser, LLMSummarizingCondenser):
            condenser = agent.condenser
            updated_condenser_llm = apply_llm_overrides(condenser.llm, overrides)
            condenser = condenser.model_copy(update={"llm": updated_condenser_llm})
        return agent.model_copy(update={"llm": updated_llm, "condenser": condenser})

    def load_or_create(
        self,
        session_id: str | None = None,
        *,
        env_overrides_enabled: bool = False,
        critic_disabled: bool = False,
    ) -> Agent | None:
        """Load an Agent and apply runtime configuration.

        Invariant:
        - If a persisted agent exists:
            * Load it from disk.
            * Apply any env overrides that are present (even partial).
        - If no persisted agent exists:
            * Require a full env spec (LLM_API_KEY + LLM_MODEL) to create
                a default Agent.
            * Otherwise, raise an error.

        Runtime configuration (tools, context, MCP, metadata, critic) is
        always applied last.

        Args:
            session_id: Optional session ID used for tool restoration and
                LLM metadata tagging.
            env_overrides_enabled: Whether env overrides are enabled.
            critic_disabled: If True, do not configure a critic.

        Returns:
            A fully configured Agent, or None if no persisted agent exists and
            env overrides are disabled.

        Raises:
            MissingEnvironmentVariablesError: If no persisted agent exists and
                required env variables are missing.
        """

        agent = self.load_from_disk()
        overrides = LLMEnvOverrides.from_env(enabled=env_overrides_enabled)

        if env_overrides_enabled:
            agent = self._ensure_agent(agent, overrides)
            agent = self._apply_env_overrides(agent, overrides)

        if agent is None:
            return None

        # Apply runtime configuration (tools, context, MCP, condenser, critic)
        return self._apply_runtime_config(
            agent,
            session_id,
            critic_disabled=critic_disabled,
        )

    def _resolve_tools(self, session_id: str | None) -> list[Tool]:
        tools = get_persisted_conversation_tools(session_id) if session_id else None
        return tools or get_default_cli_tools()

    def _with_llm_metadata(
        self, llm: LLM, *, session_id: str | None, llm_type: str
    ) -> LLM:
        if not should_set_litellm_extra_body(llm.model, llm.base_url):
            return llm
        return llm.model_copy(
            update={
                "litellm_extra_body": {
                    "metadata": get_llm_metadata(
                        model_name=llm.model,
                        llm_type=llm_type,
                        session_id=session_id,
                    )
                }
            }
        )

    def _build_agent_context(self) -> AgentContext:
        skills = load_project_skills(WORK_DIR)
        system_suffix = "\n".join(
            [
                f"Your current working directory is: {WORK_DIR}",
                f"User operating system: {get_os_description()}",
            ]
        )
        return AgentContext(
            skills=skills,
            system_message_suffix=system_suffix,
            load_user_skills=True,
            load_public_skills=True,
        )

    def _maybe_build_condenser(
        self, agent: Agent, *, session_id: str | None
    ) -> LLMSummarizingCondenser | None:
        if not (
            agent.condenser and isinstance(agent.condenser, LLMSummarizingCondenser)
        ):
            return None

        condenser_llm = self._with_llm_metadata(
            agent.condenser.llm, session_id=session_id, llm_type="condenser"
        )

        return agent.condenser.model_copy(update={"llm": condenser_llm})

    def _apply_runtime_config(
        self,
        agent: Agent,
        session_id: str | None = None,
        *,
        critic_disabled: bool = False,
    ) -> Agent:
        updated_tools = self._resolve_tools(session_id)
        updated_llm = self._with_llm_metadata(
            agent.llm, session_id=session_id, llm_type="agent"
        )

        agent_context = self._build_agent_context()

        enabled_servers = list_enabled_servers()
        mcp_config = {"mcpServers": enabled_servers} if enabled_servers else {}

        condenser = self._maybe_build_condenser(agent, session_id=session_id)

        critic = None
        if not critic_disabled:
            cli_settings = CliSettings.load()
            critic = get_default_critic(
                updated_llm, enable_critic=cli_settings.enable_critic
            )

        return agent.model_copy(
            update={
                "llm": updated_llm,
                "tools": updated_tools,
                "mcp_config": mcp_config,
                "agent_context": agent_context,
                "condenser": condenser,
                "critic": critic,
            }
        )

    def save(self, agent: Agent) -> None:
        serialized_spec = agent.model_dump_json(context={"expose_secrets": True})
        self.file_store.write(AGENT_SETTINGS_PATH, serialized_spec)

    def create_and_save_from_settings(
        self,
        llm_api_key: str,
        settings: dict[str, Any],
        default_model: str = "claude-sonnet-4-5-20250929",
    ) -> Agent:
        """Create an Agent instance from user settings and API key, then save it.

        Args:
            llm_api_key: The LLM API key to use
            settings: User settings dictionary (e.g., "llm_model", "llm_base_url")
            default_model: Default model to use if not specified in settings

        Returns:
            The created Agent instance
        """
        model = settings.get("llm_model", default_model)
        base_url = settings.get("llm_base_url")

        llm = LLM(
            model=model,
            api_key=llm_api_key,
            base_url=base_url,
            usage_id="agent",
        )

        condenser_llm = LLM(
            model=model,
            api_key=llm_api_key,
            base_url=base_url,
            usage_id="condenser",
        )

        condenser = LLMSummarizingCondenser(llm=condenser_llm)

        agent = Agent(
            llm=llm,
            tools=get_default_cli_tools(),
            mcp_config={},
            condenser=condenser,
            # Note: critic is NOT included here - it will be derived on-the-fly
        )

        # Save the agent configuration (without critic)
        self.save(agent)

        # Now add critic on-the-fly for the returned agent (not persisted)
        cli_settings = CliSettings.load()
        critic = get_default_critic(llm, enable_critic=cli_settings.enable_critic)
        if critic is not None:
            agent = agent.model_copy(update={"critic": critic})

        return agent
