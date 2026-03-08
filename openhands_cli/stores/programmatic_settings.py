from __future__ import annotations

import importlib
from typing import Any

from pydantic import Field, SecretStr

from openhands_cli.stores.agent_store import AgentStore
from openhands_cli.stores.cli_settings import (
    DEFAULT_ISSUE_THRESHOLD,
    CliSettings,
    CriticSettings,
)
from openhands_cli.utils import get_default_cli_agent


_settings_module: Any = importlib.import_module("openhands.sdk.settings")
SDKSettings = _settings_module.SDKSettings
SettingsFieldMetadata = _settings_module.SettingsFieldMetadata


class CliProgrammaticSettings(SDKSettings):
    issue_threshold: float = Field(
        default=DEFAULT_ISSUE_THRESHOLD,
        ge=0.0,
        le=1.0,
        description=(
            "Trigger iterative refinement when any individual critic issue exceeds "
            "this threshold."
        ),
        json_schema_extra={
            "openhands_settings": SettingsFieldMetadata(
                label="Issue threshold",
                section="critic",
                section_label="Critic",
                order=45,
                widget="number",
                depends_on=("enable_critic", "enable_iterative_refinement"),
                slash_command="issue-threshold",
            ).model_dump()
        },
    )
    default_cells_expanded: bool = Field(
        default=False,
        description="Expand new cells by default in the TUI.",
        json_schema_extra={
            "openhands_settings": SettingsFieldMetadata(
                label="Default cells expanded",
                section="cli",
                section_label="CLI",
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
            "openhands_settings": SettingsFieldMetadata(
                label="Auto-open plan panel",
                section="cli",
                section_label="CLI",
                order=20,
                widget="boolean",
                slash_command="auto-open-plan-panel",
            ).model_dump()
        },
    )
    enable_critic: bool = Field(
        default=True,
        description="Enable critic evaluation for the agent.",
        json_schema_extra=SDKSettings.model_fields["enable_critic"].json_schema_extra,
    )

    @classmethod
    def from_sources(
        cls,
        agent_settings: SDKSettings | None,
        cli_settings: CliSettings | None,
    ) -> CliProgrammaticSettings:
        cli_settings = cli_settings or CliSettings()
        base = agent_settings.model_dump() if agent_settings is not None else {}
        return cls(
            **base,
            enable_critic=cli_settings.critic.enable_critic,
            enable_iterative_refinement=cli_settings.critic.enable_iterative_refinement,
            critic_threshold=cli_settings.critic.critic_threshold,
            max_refinement_iterations=cli_settings.critic.max_refinement_iterations,
            issue_threshold=cli_settings.critic.issue_threshold,
            default_cells_expanded=cli_settings.default_cells_expanded,
            auto_open_plan_panel=cli_settings.auto_open_plan_panel,
        )

    @classmethod
    def load(cls, agent_store: AgentStore | None = None) -> CliProgrammaticSettings:
        agent_store = agent_store or AgentStore()
        agent = agent_store.load_from_disk()
        agent_settings = SDKSettings.from_agent(agent) if agent is not None else None
        return cls.from_sources(
            agent_settings=agent_settings, cli_settings=CliSettings.load()
        )

    def save(self, agent_store: AgentStore | None = None) -> None:
        agent_store = agent_store or AgentStore()
        existing_agent = agent_store.load_from_disk()

        effective_settings = self
        if existing_agent is not None and self.llm_api_key is None:
            effective_settings = self.model_copy(
                update={"llm_api_key": _to_secret(existing_agent.llm.api_key)}
            )

        agent = SDKSettings.model_validate(effective_settings.model_dump()).to_agent(
            existing_agent,
            agent_factory=get_default_cli_agent,
        )
        agent_store.save(agent)

        CliSettings(
            default_cells_expanded=self.default_cells_expanded,
            auto_open_plan_panel=self.auto_open_plan_panel,
            critic=CriticSettings(
                enable_critic=self.enable_critic,
                enable_iterative_refinement=self.enable_iterative_refinement,
                critic_threshold=self.critic_threshold,
                issue_threshold=self.issue_threshold,
                max_refinement_iterations=self.max_refinement_iterations,
            ),
        ).save()


def _to_secret(value: str | SecretStr | None) -> SecretStr | None:
    if value is None:
        return None
    if isinstance(value, SecretStr):
        return value
    return SecretStr(value)
