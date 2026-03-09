from __future__ import annotations

from pydantic import BaseModel, Field

from openhands.sdk.settings import (
    SETTINGS_METADATA_KEY,
    SETTINGS_SECTION_METADATA_KEY,
    AgentSettings,
    CriticSettings,
    SettingsFieldMetadata,
    SettingsSectionMetadata,
)
from openhands_cli.stores.agent_store import AgentStore
from openhands_cli.stores.cli_settings import (
    DEFAULT_ISSUE_THRESHOLD,
    CliSettings,
    CriticSettings as StoredCriticSettings,
)
from openhands_cli.utils import get_default_cli_agent


class CliCriticSettings(CriticSettings):
    enabled: bool = Field(
        default=True,
        description="Enable critic evaluation for the agent.",
        json_schema_extra=CriticSettings.model_fields["enabled"].json_schema_extra,
    )
    issue_threshold: float = Field(
        default=DEFAULT_ISSUE_THRESHOLD,
        ge=0.0,
        le=1.0,
        description=(
            "Trigger iterative refinement when any individual critic issue exceeds "
            "this threshold."
        ),
        json_schema_extra={
            SETTINGS_METADATA_KEY: SettingsFieldMetadata(
                label="Issue threshold",
                order=45,
                widget="number",
                depends_on=("enabled", "enable_iterative_refinement"),
                slash_command="issue-threshold",
            ).model_dump()
        },
    )


class CliInterfaceSettings(BaseModel):
    default_cells_expanded: bool = Field(
        default=False,
        description="Expand new cells by default in the TUI.",
        json_schema_extra={
            SETTINGS_METADATA_KEY: SettingsFieldMetadata(
                label="Default cells expanded",
                order=10,
                widget="boolean",
                slash_command="default-cells-expanded",
            ).model_dump()
        },
    )
    auto_open_plan_panel: bool = Field(
        default=True,
        description="Automatically open the plan panel when task tracking starts.",
        json_schema_extra={
            SETTINGS_METADATA_KEY: SettingsFieldMetadata(
                label="Auto-open plan panel",
                order=20,
                widget="boolean",
                slash_command="auto-open-plan-panel",
            ).model_dump()
        },
    )


class CliProgrammaticSettings(AgentSettings):
    critic: CliCriticSettings = Field(
        default_factory=CliCriticSettings,
        description="Critic settings for the CLI agent.",
        json_schema_extra=AgentSettings.model_fields["critic"].json_schema_extra,
    )
    cli: CliInterfaceSettings = Field(
        default_factory=CliInterfaceSettings,
        description="CLI interface settings.",
        json_schema_extra={
            SETTINGS_SECTION_METADATA_KEY: SettingsSectionMetadata(
                key="cli",
                label="CLI",
                order=40,
            ).model_dump()
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
        critic = dict(base.get("critic", {}))
        critic.update(
            {
                "enabled": cli_settings.critic.enable_critic,
                "enable_iterative_refinement": (
                    cli_settings.critic.enable_iterative_refinement
                ),
                "threshold": cli_settings.critic.critic_threshold,
                "max_refinement_iterations": (
                    cli_settings.critic.max_refinement_iterations
                ),
                "issue_threshold": cli_settings.critic.issue_threshold,
            }
        )
        base["critic"] = critic
        base["cli"] = {
            "default_cells_expanded": cli_settings.default_cells_expanded,
            "auto_open_plan_panel": cli_settings.auto_open_plan_panel,
        }
        return cls(**base)

    @classmethod
    def load(cls, agent_store: AgentStore | None = None) -> CliProgrammaticSettings:
        agent_store = agent_store or AgentStore()
        agent = agent_store.load_from_disk()
        agent_settings = AgentSettings.from_agent(agent) if agent is not None else None
        return cls.from_sources(
            agent_settings=agent_settings,
            cli_settings=CliSettings.load(),
        )

    def save(self, agent_store: AgentStore | None = None) -> None:
        agent_store = agent_store or AgentStore()
        existing_agent = agent_store.load_from_disk()

        agent_settings = AgentSettings.model_validate(
            {
                "llm": self.llm.model_dump(mode="python"),
                "condenser": self.condenser.model_dump(mode="python"),
                "critic": self.critic.model_dump(
                    mode="python",
                    exclude={"issue_threshold"},
                ),
            }
        )
        agent = agent_settings.to_agent(
            existing_agent,
            agent_factory=get_default_cli_agent,
        )
        agent_store.save(agent)

        CliSettings(
            default_cells_expanded=self.cli.default_cells_expanded,
            auto_open_plan_panel=self.cli.auto_open_plan_panel,
            critic=StoredCriticSettings(
                enable_critic=self.critic.enabled,
                enable_iterative_refinement=self.critic.enable_iterative_refinement,
                critic_threshold=self.critic.threshold,
                issue_threshold=self.critic.issue_threshold,
                max_refinement_iterations=self.critic.max_refinement_iterations,
            ),
        ).save()

