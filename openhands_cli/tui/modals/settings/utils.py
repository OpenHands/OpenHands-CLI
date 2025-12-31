from typing import Any, Literal

from pydantic import BaseModel, SecretStr, field_validator

from openhands.sdk import LLM, Agent, LLMSummarizingCondenser
from openhands_cli.stores import AgentStore
from openhands_cli.utils import (
    get_default_cli_agent,
    get_llm_metadata,
    should_set_litellm_extra_body,
)


agent_store = AgentStore()


class SettingsFormData(BaseModel):
    """Raw values captured from the SettingsScreen UI."""

    # "basic" = provider/model select, "advanced" = custom model + base URL
    mode: Literal["basic", "advanced"]

    # Basic-mode fields
    provider: str | None = None
    model: str | None = None

    # Advanced-mode fields
    custom_model: str | None = None
    base_url: str | None = None

    # API key typed into the UI (may be empty -> should keep existing)
    api_key_input: str | None = None

    # Whether the user wants memory condensation enabled
    memory_condensation_enabled: bool = True

    @field_validator("provider", "model", "custom_model", "base_url", "api_key_input")
    @classmethod
    def strip_strings(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    def resolve_data_fields(self, existing_agent: Agent | None):
        # Check advance mode requirements
        if self.mode == "advanced":
            if not self.custom_model:
                raise Exception("Custom model is required in advanced mode")
            if not self.base_url:
                raise Exception("Base URL is required in advanced mode")

            self.provider = None
            self.model = None

        # Check basic mode requirements
        if self.mode == "basic":
            if not self.provider:
                raise Exception("Please select a provider")

            if not self.model:
                raise Exception("Please select a model")

            self.custom_model = None
            self.base_url = None

        # Check API key
        if not self.api_key_input and existing_agent:
            existing_llm_api_key = existing_agent.llm.api_key
            existing_llm_api_key = (
                existing_llm_api_key.get_secret_value()
                if isinstance(existing_llm_api_key, SecretStr)
                else existing_llm_api_key
            )
            self.api_key_input = existing_llm_api_key

        if not self.api_key_input:
            raise Exception("API Key is required")

    def get_full_model_name(self):
        if self.mode == "advanced":
            return str(self.custom_model)

        model_str = str(self.model)
        full_model = (
            f"{self.provider}/{model_str}" if "/" not in model_str else model_str
        )
        return full_model


class SettingsSaveResult(BaseModel):
    """Result of attempting to save settings."""

    success: bool
    error_message: str | None = None


def save_settings(
    data: SettingsFormData, existing_agent: Agent | None
) -> SettingsSaveResult:
    try:
        data.resolve_data_fields(existing_agent)
        extra_kwargs: dict[str, Any] = {}

        full_model = data.get_full_model_name()

        if should_set_litellm_extra_body(full_model):
            extra_kwargs["litellm_extra_body"] = {
                "metadata": get_llm_metadata(model_name=full_model, llm_type="agent")
            }

        if full_model.startswith("openhands/") and data.base_url is None:
            data.base_url = "https://llm-proxy.app.all-hands.dev/"

        llm = LLM(
            model=full_model,
            api_key=data.api_key_input,
            base_url=data.base_url,
            usage_id="agent",
            **extra_kwargs,
        )

        agent = existing_agent or get_default_cli_agent(llm=llm)
        agent = agent.model_copy(update={"llm": llm})

        condenser_llm = llm.model_copy(update={"usage_id": "condenser"})
        if should_set_litellm_extra_body(full_model):
            condenser_llm = condenser_llm.model_copy(
                update={
                    "litellm_extra_body": {
                        "metadata": get_llm_metadata(
                            model_name=full_model, llm_type="condenser"
                        )
                    }
                }
            )

        if agent.condenser and isinstance(agent.condenser, LLMSummarizingCondenser):
            agent = agent.model_copy(
                update={
                    "condenser": agent.condenser.model_copy(
                        update={"llm": condenser_llm}
                    )
                }
            )

        if data.memory_condensation_enabled and not agent.condenser:
            # Enable condensation
            condenser_llm = agent.llm.model_copy(update={"usage_id": "condenser"})
            condenser = LLMSummarizingCondenser(llm=condenser_llm)
            agent = agent.model_copy(update={"condenser": condenser})
        elif not data.memory_condensation_enabled and agent.condenser:
            # Disable condensation
            agent = agent.model_copy(update={"condenser": None})

        agent_store.save(agent)

        return SettingsSaveResult(success=True, error_message=None)
    except Exception as e:
        return SettingsSaveResult(success=False, error_message=str(e))
