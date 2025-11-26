# openhands_cli/settings/store.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp.mcp_config import MCPConfig
from prompt_toolkit import HTML, print_formatted_text

from openhands.sdk import Agent, AgentContext, LocalFileStore
from openhands.sdk.context import load_skills_from_dir
from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands.tools.preset.default import get_default_tools
from openhands_cli.locations import (
    AGENT_SETTINGS_PATH,
    MCP_CONFIG_FILE,
    PERSISTENCE_DIR,
    WORK_DIR,
)
from openhands_cli.utils import get_llm_metadata, should_set_litellm_extra_body


class AgentStore:
    """Single source of truth for persisting/retrieving AgentSpec."""

    def __init__(self) -> None:
        self.file_store = LocalFileStore(root=PERSISTENCE_DIR)

    def load_mcp_configuration(self) -> dict[str, Any]:
        try:
            mcp_config_path = Path(self.file_store.root) / MCP_CONFIG_FILE
            mcp_config = MCPConfig.from_file(mcp_config_path)
            return mcp_config.to_dict()["mcpServers"]
        except Exception:
            return {}

    def load_project_skills(self) -> list:
        """Load skills project-specific directories."""
        all_skills = []

        # Load project-specific skills from .openhands/skills and legacy microagents
        project_skills_dirs = [
            Path(WORK_DIR) / ".openhands" / "skills",
            Path(WORK_DIR) / ".openhands" / "microagents",  # Legacy support
        ]

        for project_skills_dir in project_skills_dirs:
            if project_skills_dir.exists():
                try:
                    repo_skills, knowledge_skills = load_skills_from_dir(
                        project_skills_dir
                    )
                    project_skills = list(repo_skills.values()) + list(
                        knowledge_skills.values()
                    )
                    all_skills.extend(project_skills)
                except Exception:
                    pass

        return all_skills

    def load(self, session_id: str | None = None) -> Agent | None:
        try:
            str_spec = self.file_store.read(AGENT_SETTINGS_PATH)
            agent = Agent.model_validate_json(str_spec)

            # Update tools with most recent working directory
            updated_tools = get_default_tools(enable_browser=False)

            # Load skills from user directories and project-specific directories
            skills = self.load_project_skills()

            agent_context = AgentContext(
                skills=skills,
                system_message_suffix=f"You current working directory is: {WORK_DIR}",
                load_user_skills=True,
            )

            mcp_config: dict = self.load_mcp_configuration()

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
                    "mcp_config": {"mcpServers": mcp_config} if mcp_config else {},
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
