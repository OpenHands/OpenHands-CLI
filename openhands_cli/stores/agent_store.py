# openhands_cli/settings/store.py
from __future__ import annotations

import json
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


# Current version of the agent settings format
AGENT_SETTINGS_VERSION = "v1"


def _serialize_agent_minimal(agent: Agent) -> str:
    """Serialize agent with minimal data, preserving only user-configured values.

    Uses exclude_defaults=True to omit SDK default values, ensuring users
    automatically get updated defaults when the SDK changes. Discriminator
    fields (like 'kind') are preserved for polymorphic deserialization.

    The output includes a _version field to track the settings format version.
    """
    dump = agent.model_dump(exclude_defaults=True, context={"expose_secrets": True})

    # Preserve discriminator fields for polymorphic types
    if agent.condenser is not None:
        if "condenser" not in dump:
            dump["condenser"] = {}
        dump["condenser"]["kind"] = agent.condenser.kind

    # Add version field
    dump["_version"] = AGENT_SETTINGS_VERSION

    return json.dumps(dump)


class AgentStore:
    """Single source of truth for persisting/retrieving AgentSpec."""

    def __init__(self) -> None:
        self.file_store = LocalFileStore(root=PERSISTENCE_DIR)

    def _get_settings_version(self, data: dict[str, Any]) -> str:
        """Get the version of the settings format.

        Returns 'v0' for legacy settings (no version field), otherwise returns
        the value of the _version field.
        """
        return data.get("_version", "v0")

    def load(self, session_id: str | None = None) -> Agent | None:
        try:
            str_spec = self.file_store.read(AGENT_SETTINGS_PATH)

            # Parse JSON to check version and prepare for migration
            raw_data = json.loads(str_spec)
            settings_version = self._get_settings_version(raw_data)

            # Remove _version field before validating as Agent model
            raw_data.pop("_version", None)

            agent = Agent.model_validate(raw_data)

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
            llm_update: dict[str, Any] = {}
            if should_set_litellm_extra_body(agent.llm.model):
                llm_update["litellm_extra_body"] = {
                    "metadata": get_llm_metadata(
                        model_name=agent.llm.model,
                        llm_type="agent",
                        session_id=session_id,
                    )
                }
            updated_llm = agent.llm.model_copy(update=llm_update)

            # Always create a fresh condenser with current SDK defaults if condensation
            # is enabled. This ensures users get the latest condenser settings
            # (e.g., max_size, keep_first) without needing to reconfigure.
            condenser = None
            if agent.condenser and isinstance(agent.condenser, LLMSummarizingCondenser):
                condenser_llm_update: dict[str, Any] = {}
                if should_set_litellm_extra_body(agent.condenser.llm.model):
                    condenser_llm_update["litellm_extra_body"] = {
                        "metadata": get_llm_metadata(
                            model_name=agent.condenser.llm.model,
                            llm_type="condenser",
                            session_id=session_id,
                        )
                    }
                condenser_llm = agent.condenser.llm.model_copy(
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

            # If loading from v0 format, re-save in v1 format for future loads
            if settings_version == "v0":
                self.save(agent)

            return agent
        except FileNotFoundError:
            return None
        except Exception:
            print_formatted_text(
                HTML("\n<red>Agent configuration file is corrupted!</red>")
            )
            return None

    def save(self, agent: Agent) -> None:
        serialized_spec = _serialize_agent_minimal(agent)
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
