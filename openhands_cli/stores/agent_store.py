# openhands_cli/settings/store.py
from __future__ import annotations

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


class AgentStore:
    """Single source of truth for persisting/retrieving AgentSpec."""

    def __init__(self) -> None:
        self.file_store = LocalFileStore(root=PERSISTENCE_DIR)

    def load(self, session_id: str | None = None) -> Agent | None:
        try:
            str_spec = self.file_store.read(AGENT_SETTINGS_PATH)
            agent = Agent.model_validate_json(str_spec)

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

            # Update LLM metadata with current information
            llm_update = {}
            if should_set_litellm_extra_body(agent.llm.model):
                llm_update["litellm_extra_body"] = {
                    "metadata": get_llm_metadata(
                        model_name=agent.llm.model,
                        llm_type="agent",
                        session_id=session_id,
                    )
                }
            updated_llm = agent.llm.model_copy(update=llm_update)

            condenser_updates = {}
            if agent.condenser and isinstance(agent.condenser, LLMSummarizingCondenser):
                condenser_llm_update = {}
                if should_set_litellm_extra_body(agent.condenser.llm.model):
                    condenser_llm_update["litellm_extra_body"] = {
                        "metadata": get_llm_metadata(
                            model_name=agent.condenser.llm.model,
                            llm_type="condenser",
                            session_id=session_id,
                        )
                    }
                condenser_updates["llm"] = agent.condenser.llm.model_copy(
                    update=condenser_llm_update
                )

            # Update tools and context
            agent = agent.model_copy(
                update={
                    "llm": updated_llm,
                    "tools": updated_tools,
                    "mcp_config": {"mcpServers": enabled_servers}
                    if enabled_servers
                    else {},
                    "agent_context": agent_context,
                    "condenser": agent.condenser.model_copy(update=condenser_updates)
                    if agent.condenser
                    else None,
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
        base_url: str = "https://llm-proxy.app.all-hands.dev/",
        default_model: str = "claude-sonnet-4-5-20250929",
    ) -> Agent:
        """Create an Agent instance from user settings and API key, then save it.

        Args:
            llm_api_key: The LLM API key to use
            settings: User settings dictionary containing model and other config
            base_url: Base URL for the LLM service
            default_model: Default model to use if not specified in settings

        Returns:
            The created Agent instance
        """
        model = settings.get("llm_model", default_model)

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
            tools=get_default_tools(enable_browser=False),
            mcp_config={},
            condenser=condenser,
        )

        # Save the agent configuration
        self.save(agent)

        return agent
