# openhands_cli/settings/store.py
from __future__ import annotations

import logging
from pathlib import Path
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
from openhands.sdk.context.skills import Skill, load_skills_from_dir
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


logger = logging.getLogger(__name__)


def load_third_party_skills_from_work_dir(work_dir: str | Path) -> list[Skill]:
    """Load third-party skill files (AGENTS.md, etc.) directly from work directory.

    This function addresses a bug in the SDK where third-party skill files like
    AGENTS.md are only loaded if .openhands/skills or .openhands/microagents
    directories exist. This function ensures these files are loaded regardless
    of whether those directories exist.

    Uses the SDK's load_skills_from_dir() which already has logic to check for
    third-party files in the repo root (calculated as skill_dir.parent.parent).
    By passing the expected skills directory path, even if it doesn't exist,
    the SDK will still check for third-party files in the work directory.

    Additionally scans the directory for case-insensitive matches since the SDK's
    variant matching doesn't handle mixed case (e.g., "AGENTS.md").

    Args:
        work_dir: Path to the working directory (project root).

    Returns:
        List of Skill objects loaded from third-party files.
    """
    if isinstance(work_dir, str):
        work_dir = Path(work_dir)

    skills = []
    seen_names: set[str] = set()

    # Use SDK's load_skills_from_dir() which handles third-party files
    # when the skills directory path is provided (even if it doesn't exist)
    skills_dir = work_dir / ".openhands" / "skills"
    try:
        repo_skills, _ = load_skills_from_dir(skills_dir)
        for name, skill in repo_skills.items():
            if name not in seen_names:
                skills.append(skill)
                seen_names.add(name)
    except Exception as e:
        logger.debug(f"SDK load_skills_from_dir failed: {e}")

    # Scan directory for case-insensitive matches (SDK doesn't handle mixed case)
    third_party_filenames_lower = {
        name.lower() for name in Skill.PATH_TO_THIRD_PARTY_SKILL_NAME.keys()
    }

    try:
        for file_path in work_dir.iterdir():
            if not file_path.is_file():
                continue

            if file_path.name.lower() in third_party_filenames_lower:
                try:
                    skill = Skill.load(file_path)
                    if skill.name not in seen_names:
                        skills.append(skill)
                        seen_names.add(skill.name)
                except Exception as e:
                    logger.warning(
                        f"Failed to load third-party skill from {file_path}: {e}"
                    )
    except OSError as e:
        logger.warning(f"Failed to scan work directory {work_dir}: {e}")

    return skills


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

            # Load third-party skill files (AGENTS.md, etc.) directly from work dir
            # This ensures they are loaded even if .openhands/skills doesn't exist
            # (workaround for SDK bug where third-party files are only checked
            # inside load_skills_from_dir which requires skills directory to exist)
            third_party_skills = load_third_party_skills_from_work_dir(WORK_DIR)

            # Merge third-party skills with project skills, avoiding duplicates
            existing_skill_names = {s.name for s in skills}
            for skill in third_party_skills:
                if skill.name not in existing_skill_names:
                    skills.append(skill)
                    existing_skill_names.add(skill.name)

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
            tools=get_default_tools(enable_browser=False),
            mcp_config={},
            condenser=condenser,
        )

        # Save the agent configuration
        self.save(agent)

        return agent
