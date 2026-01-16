# openhands_cli/settings/store.py
from __future__ import annotations

import os
from typing import Any

from prompt_toolkit import HTML, print_formatted_text

from openhands.sdk import (
    LLM,
    Agent,
    AgentContext,
    LLMSummarizingCondenser,
    LocalFileStore,
)
from openhands.sdk.context import load_project_skills
from openhands.tools.preset.default import get_default_tools
from openhands_cli.locations import (
    AGENT_SETTINGS_PATH,
    PERSISTENCE_DIR,
    WORK_DIR,
)
from openhands_cli.mcp.mcp_utils import list_enabled_servers
from openhands_cli.utils import (
    get_llm_metadata,
    get_os_description,
    should_set_litellm_extra_body,
)


DEFAULT_LLM_BASE_URL = "https://llm-proxy.app.all-hands.dev/"

# Environment variable names for LLM configuration
ENV_LLM_API_KEY = "LLM_API_KEY"
ENV_LLM_BASE_URL = "LLM_BASE_URL"
ENV_LLM_MODEL = "LLM_MODEL"


def get_env_llm_overrides() -> dict[str, str]:
    """Get LLM configuration overrides from environment variables.

    Returns:
        Dictionary with keys 'api_key', 'base_url', 'model' for any
        environment variables that are set. Empty dict if none are set.
    """
    overrides: dict[str, str] = {}

    api_key = os.environ.get(ENV_LLM_API_KEY)
    if api_key:
        overrides["api_key"] = api_key

    base_url = os.environ.get(ENV_LLM_BASE_URL)
    if base_url:
        overrides["base_url"] = base_url

    model = os.environ.get(ENV_LLM_MODEL)
    if model:
        overrides["model"] = model

    return overrides


def apply_llm_overrides(llm: LLM, overrides: dict[str, str]) -> LLM:
    """Apply environment variable overrides to an LLM instance.

    Args:
        llm: The LLM instance to update
        overrides: Dictionary of overrides from get_env_llm_overrides()

    Returns:
        Updated LLM instance with overrides applied
    """
    if not overrides:
        return llm

    # Convert api_key to SecretStr if present (LLM model expects SecretStr)
    from pydantic import SecretStr

    update_dict: dict[str, str | SecretStr] = dict(overrides)
    if "api_key" in update_dict:
        update_dict["api_key"] = SecretStr(update_dict["api_key"])

    return llm.model_copy(update=update_dict)


def resolve_llm_base_url(
    settings: dict[str, Any],
    base_url: str | None = None,
) -> str:
    candidate = base_url if base_url is not None else settings.get("llm_base_url")
    if candidate is None:
        return DEFAULT_LLM_BASE_URL

    if isinstance(candidate, str):
        candidate = candidate.strip()
    else:
        candidate = str(candidate).strip()

    return candidate or DEFAULT_LLM_BASE_URL


class AgentStore:
    """Single source of truth for persisting/retrieving AgentSpec."""

    def __init__(self) -> None:
        self.file_store = LocalFileStore(root=PERSISTENCE_DIR)

    def load(self, session_id: str | None = None) -> Agent | None:
        try:
            str_spec = self.file_store.read(AGENT_SETTINGS_PATH)
            agent = Agent.model_validate_json(str_spec)

            # Get environment variable overrides (these take precedence over
            # stored settings and are NOT persisted to disk)
            env_overrides = get_env_llm_overrides()

            # Update tools with most recent working directory
            updated_tools = get_default_tools(enable_browser=False)

            # Load skills from user directories and project-specific directories
            skills = load_project_skills(WORK_DIR)

            system_suffix = "\n".join(
                [
                    f"Your current working directory is: {WORK_DIR}",
                    f"User operating system: {get_os_description()}",
                ]
            )

            agent_context = AgentContext(
                skills=skills,
                system_message_suffix=system_suffix,
                load_user_skills=True,
                load_public_skills=True,
            )

            # Get only enabled MCP servers
            enabled_servers = list_enabled_servers()

            # Apply environment variable overrides first, then update metadata
            updated_llm = apply_llm_overrides(agent.llm, env_overrides)

            # Update LLM metadata with current information
            llm_update: dict[str, Any] = {}
            if should_set_litellm_extra_body(updated_llm.model):
                llm_update["litellm_extra_body"] = {
                    "metadata": get_llm_metadata(
                        model_name=updated_llm.model,
                        llm_type="agent",
                        session_id=session_id,
                    )
                }
            if llm_update:
                updated_llm = updated_llm.model_copy(update=llm_update)

            # Always create a fresh condenser with current defaults if condensation
            # is enabled. This ensures users get the latest condenser settings
            # (e.g., max_size, keep_first) without needing to reconfigure.
            condenser = None
            if agent.condenser and isinstance(agent.condenser, LLMSummarizingCondenser):
                # Apply environment variable overrides to condenser LLM as well
                condenser_llm = apply_llm_overrides(
                    agent.condenser.llm, env_overrides
                )

                condenser_llm_update: dict[str, Any] = {}
                if should_set_litellm_extra_body(condenser_llm.model):
                    condenser_llm_update["litellm_extra_body"] = {
                        "metadata": get_llm_metadata(
                            model_name=condenser_llm.model,
                            llm_type="condenser",
                            session_id=session_id,
                        )
                    }
                if condenser_llm_update:
                    condenser_llm = condenser_llm.model_copy(
                        update=condenser_llm_update
                    )
                condenser = LLMSummarizingCondenser(llm=condenser_llm)

            # Update tools and context
            agent = agent.model_copy(
                update={
                    "llm": updated_llm,
                    "tools": updated_tools,
                    "mcp_config": {"mcpServers": enabled_servers}
                    if enabled_servers
                    else {},
                    "agent_context": agent_context,
                    "condenser": condenser,
                }
            )

            return agent
        except FileNotFoundError:
            return None
        except Exception:
            print_formatted_text(
                HTML("\n<red>Agent configuration file is corrupted!</red>")
            )
            return None

    def save(self, agent: Agent) -> None:
        serialized_spec = agent.model_dump_json(context={"expose_secrets": True})
        self.file_store.write(AGENT_SETTINGS_PATH, serialized_spec)

    def create_and_save_from_settings(
        self,
        llm_api_key: str,
        settings: dict[str, Any],
        base_url: str | None = None,
        default_model: str = "claude-sonnet-4-5-20250929",
    ) -> Agent:
        """Create an Agent instance from user settings and API key, then save it.

        Args:
            llm_api_key: The LLM API key to use
            settings: User settings dictionary containing model and other config
            base_url: Base URL for the LLM service (defaults to
                `settings['llm_base_url']`
            )
            default_model: Default model to use if not specified in settings

        Returns:
            The created Agent instance
        """
        model = settings.get("llm_model", default_model)

        resolved_base_url = resolve_llm_base_url(settings, base_url=base_url)

        llm = LLM(
            model=model,
            api_key=llm_api_key,
            base_url=resolved_base_url,
            usage_id="agent",
        )

        condenser_llm = LLM(
            model=model,
            api_key=llm_api_key,
            base_url=resolved_base_url,
            usage_id="condenser",
        )

        condenser = LLMSummarizingCondenser(llm=condenser_llm)

        agent = Agent(
            llm=llm,
            tools=get_default_tools(enable_browser=False),
            mcp_config={},
            condenser=condenser,
        )

        # Save the agent configuration
        self.save(agent)

        return agent
