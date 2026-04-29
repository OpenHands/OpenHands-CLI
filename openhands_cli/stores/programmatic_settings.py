from __future__ import annotations

import json

from pydantic import BaseModel, Field

from openhands.sdk.agent import Agent
from openhands.sdk.settings import (
    SETTINGS_SECTION_METADATA_KEY,
    AgentSettings,
    SettingProminence,
    SettingsSectionMetadata,
    field_meta,
)
from openhands_cli.locations import PROGRAMMATIC_SETTINGS_PATH
from openhands_cli.stores.agent_store import AgentStore
from openhands_cli.stores.cli_settings import CliSettings, CriticSettings
from openhands_cli.utils import get_default_cli_agent


class CliInterfaceSettings(BaseModel):
    default_cells_expanded: bool = Field(
        default=False,
        description="Expand new cells by default in the TUI.",
        json_schema_extra=field_meta(
            SettingProminence.MAJOR,
            label="Default cells expanded",
        ),
    )
    auto_open_plan_panel: bool = Field(
        default=True,
        description="Automatically open the plan panel when task tracking starts.",
        json_schema_extra=field_meta(
            SettingProminence.MAJOR,
            label="Auto-open plan panel",
        ),
    )


class CliProgrammaticSettings(AgentSettings):
    verification: CriticSettings = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
        default_factory=CriticSettings,
        description="Verification settings for the CLI agent.",
        json_schema_extra=AgentSettings.model_fields["verification"].json_schema_extra,
    )
    cli: CliInterfaceSettings = Field(
        default_factory=CliInterfaceSettings,
        description="CLI interface settings.",
        json_schema_extra={
            SETTINGS_SECTION_METADATA_KEY: SettingsSectionMetadata(
                key="cli",
                label="CLI",
            ).model_dump(mode="json")
        },
    )

    @classmethod
    def from_sources(
        cls,
        agent_settings: AgentSettings | None,
        cli_settings: CliSettings | None,
    ) -> CliProgrammaticSettings:
        cli_settings = cli_settings or CliSettings()
        base = (
            agent_settings.model_dump(mode="python")
            if agent_settings is not None
            else {}
        )

        legacy_critic = cli_settings.critic
        if legacy_critic is not None:
            verification = dict(base.get("verification", {}))
            verification.update(
                legacy_critic.model_dump(mode="python", exclude_unset=True)
            )
            base["verification"] = verification

        base["cli"] = {
            "default_cells_expanded": cli_settings.default_cells_expanded,
            "auto_open_plan_panel": cli_settings.auto_open_plan_panel,
        }
        return cls(**base)

    @classmethod
    def load(cls, agent_store: AgentStore | None = None) -> CliProgrammaticSettings:
        agent_store = agent_store or AgentStore()
        agent_settings = _load_agent_settings_snapshot(agent_store)
        if agent_settings is None:
            agent = agent_store.load_from_disk()
            agent_settings = (
                _agent_settings_from_agent(agent) if agent is not None else None
            )
        return cls.from_sources(
            agent_settings=agent_settings,
            cli_settings=CliSettings.load(),
        )

    def save(self, agent_store: AgentStore | None = None) -> None:
        agent_store = agent_store or AgentStore()
        existing_agent = agent_store.load_from_disk()

        agent_settings = AgentSettings.model_validate(
            self.model_dump(
                mode="python",
                exclude={"cli": True},
            )
        )
        _save_agent_settings_snapshot(agent_store, agent_settings)

        agent = _update_agent_from_settings(agent_settings, existing_agent)
        agent_store.save(agent)

        CliSettings(
            default_cells_expanded=self.cli.default_cells_expanded,
            auto_open_plan_panel=self.cli.auto_open_plan_panel,
            critic=self.verification,
        ).save(include_critic=True)


def _load_agent_settings_snapshot(
    agent_store: AgentStore,
) -> AgentSettings | None:
    try:
        raw = agent_store.file_store.read(PROGRAMMATIC_SETTINGS_PATH)
    except FileNotFoundError:
        return None

    try:
        return AgentSettings.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return None


def _save_agent_settings_snapshot(
    agent_store: AgentStore,
    settings: AgentSettings,
) -> None:
    agent_store.file_store.write(
        PROGRAMMATIC_SETTINGS_PATH,
        settings.model_dump_json(context={"expose_secrets": True}),
    )


def _agent_settings_from_agent(agent: Agent) -> AgentSettings:
    condenser: dict[str, object]
    if agent.condenser is None:
        condenser = {"enabled": False}
    else:
        condenser = {"enabled": True}
        max_size = getattr(agent.condenser, "max_size", None)
        if isinstance(max_size, int):
            condenser["max_size"] = max_size

    data: dict[str, object] = {
        "llm": agent.llm,
        "tools": agent.tools,
        "mcp_config": agent.mcp_config or None,
        "condenser": condenser,
        "verification": _verification_from_agent(agent),
    }
    if agent.agent_context is not None:
        data["agent_context"] = agent.agent_context

    return AgentSettings.model_validate(data)


def _verification_from_agent(agent: Agent) -> CriticSettings:
    critic = agent.critic
    if critic is None:
        return CriticSettings(critic_enabled=False)

    data: dict[str, object] = {
        "critic_enabled": True,
        "critic_mode": critic.mode,
    }

    iterative_refinement = critic.iterative_refinement
    if iterative_refinement is not None:
        data.update(
            {
                "enable_iterative_refinement": True,
                "critic_threshold": iterative_refinement.success_threshold,
                "max_refinement_iterations": iterative_refinement.max_iterations,
            }
        )
        issue_threshold = getattr(iterative_refinement, "issue_threshold", None)
        if isinstance(issue_threshold, int | float):
            data["issue_threshold"] = float(issue_threshold)

    server_url = getattr(critic, "server_url", None)
    if isinstance(server_url, str):
        data["critic_server_url"] = server_url

    model_name = getattr(critic, "model_name", None)
    if isinstance(model_name, str):
        data["critic_model_name"] = model_name

    return CriticSettings.model_validate(data)


def _update_agent_from_settings(
    settings: AgentSettings,
    existing_agent: Agent | None,
) -> Agent:
    base_agent = existing_agent or get_default_cli_agent(settings.llm)
    return base_agent.model_copy(
        update={
            "llm": settings.llm,
            "mcp_config": settings._serialize_mcp_config(settings.mcp_config),
            "agent_context": settings.agent_context,
            "condenser": settings.build_condenser(settings.llm),
            "critic": settings.build_critic(),
        }
    )
