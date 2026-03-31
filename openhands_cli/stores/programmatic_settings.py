from __future__ import annotations

from pydantic import BaseModel, Field

from openhands.sdk.agent import Agent
from openhands.sdk.settings import (
    SETTINGS_SECTION_METADATA_KEY,
    AgentSettings,
    SettingProminence,
    SettingsSectionMetadata,
    VerificationSettings,
    field_meta,
)
from openhands_cli.stores.agent_store import AgentStore
from openhands_cli.stores.cli_settings import (
    DEFAULT_ISSUE_THRESHOLD,
    CliSettings,
    CriticSettings as StoredCriticSettings,
)
from openhands_cli.utils import get_default_cli_agent


class CliVerificationSettings(VerificationSettings):
    issue_threshold: float = Field(
        default=DEFAULT_ISSUE_THRESHOLD,
        ge=0.0,
        le=1.0,
        description=(
            "Trigger iterative refinement when any individual critic issue exceeds "
            "this threshold."
        ),
        json_schema_extra=field_meta(
            SettingProminence.MINOR,
            label="Issue threshold",
            depends_on=("critic_enabled", "enable_iterative_refinement"),
        ),
    )


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
    verification: CliVerificationSettings = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
        default_factory=CliVerificationSettings,
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
        verification = dict(base.get("verification", {}))
        verification.update(
            {
                "critic_enabled": cli_settings.critic.enable_critic,
                "enable_iterative_refinement": (
                    cli_settings.critic.enable_iterative_refinement
                ),
                "critic_threshold": cli_settings.critic.critic_threshold,
                "max_refinement_iterations": (
                    cli_settings.critic.max_refinement_iterations
                ),
                "issue_threshold": cli_settings.critic.issue_threshold,
            }
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
                exclude={"cli": True, "verification": {"issue_threshold"}},
            )
        )
        agent = _update_agent_from_settings(agent_settings, existing_agent)
        agent_store.save(agent)

        CliSettings(
            default_cells_expanded=self.cli.default_cells_expanded,
            auto_open_plan_panel=self.cli.auto_open_plan_panel,
            critic=StoredCriticSettings(
                enable_critic=self.verification.critic_enabled,
                enable_iterative_refinement=self.verification.enable_iterative_refinement,
                critic_threshold=self.verification.critic_threshold,
                issue_threshold=self.verification.issue_threshold,
                max_refinement_iterations=self.verification.max_refinement_iterations,
            ),
        ).save()


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
    }
    if agent.agent_context is not None:
        data["agent_context"] = agent.agent_context

    return AgentSettings.model_validate(data)


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
