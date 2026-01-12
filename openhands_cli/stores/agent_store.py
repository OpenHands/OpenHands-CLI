# openhands_cli/settings/store.py
from __future__ import annotations

import json
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
from openhands.sdk.conversation.persistence_const import BASE_STATE
from openhands.sdk.tool import Tool
from openhands_cli.locations import (
    AGENT_SETTINGS_PATH,
    CONVERSATIONS_DIR,
    PERSISTENCE_DIR,
    WORK_DIR,
)
from openhands_cli.mcp.mcp_utils import list_enabled_servers
from openhands_cli.utils import (
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


class AgentStore:
    """Single source of truth for persisting/retrieving AgentSpec."""

    def __init__(self) -> None:
        self.file_store = LocalFileStore(root=PERSISTENCE_DIR)

    def load(self, session_id: str | None = None) -> Agent | None:
        try:
            str_spec = self.file_store.read(AGENT_SETTINGS_PATH)
            agent = Agent.model_validate_json(str_spec)

            # Determine which tools to use:
            # - If resuming a conversation, use the tools from the persisted state
            # - If creating a new conversation, use the default CLI tools
            updated_tools = (
                get_persisted_conversation_tools(session_id) if session_id else None
            )
            updated_tools = updated_tools or get_default_cli_tools()

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

            # Always create a fresh condenser with current defaults if condensation
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
            tools=get_default_cli_tools(),
            mcp_config={},
            condenser=condenser,
        )

        # Save the agent configuration
        self.save(agent)

        return agent
