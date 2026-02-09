from typing import Any, Literal

from pydantic import BaseModel, SecretStr, field_validator

from openhands.sdk import LLM, Agent, LLMSummarizingCondenser
from openhands.sdk.llm import OpenAISubscriptionAuth
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

    # Whether this is a ChatGPT subscription auth (no API key needed)
    is_chatgpt_subscription: bool = False

    @field_validator("provider", "model", "custom_model", "base_url", "api_key_input")
    @classmethod
    def strip_strings(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    def resolve_data_fields(self, existing_agent: Agent | None) -> None:
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

        # Skip API key validation for ChatGPT subscription
        if self.is_chatgpt_subscription:
            return

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

    def get_full_model_name(self) -> str:
        if self.mode == "advanced":
            return str(self.custom_model)

        model_str = str(self.model)

        # For ChatGPT subscription, use openai/ prefix for the model
        if self.is_chatgpt_subscription:
            return f"openai/{model_str}"

        # Always add provider prefix - litellm requires it for routing.
        # Even if model contains '/' (e.g. "openai/gpt-4.1" from openrouter)
        # See: https://docs.litellm.ai/docs/providers
        return f"{self.provider}/{model_str}"


class SettingsSaveResult(BaseModel):
    """Result of attempting to save settings."""

    success: bool
    error_message: str | None = None


def save_settings(
    data: SettingsFormData,
    existing_agent: Agent | None,
    chatgpt_auth: OpenAISubscriptionAuth | None = None,
) -> SettingsSaveResult:
    try:
        data.resolve_data_fields(existing_agent)

        full_model = data.get_full_model_name()

        # Handle ChatGPT subscription auth
        if data.is_chatgpt_subscription:
            if chatgpt_auth is None:
                return SettingsSaveResult(
                    success=False,
                    error_message="ChatGPT auth handler not provided",
                )

            # Get the model name without provider prefix for create_llm
            model_name = str(data.model)
            llm = chatgpt_auth.create_llm(model=model_name, usage_id="agent")
        else:
            # Standard API key based auth
            extra_kwargs: dict[str, Any] = {}

            if full_model.startswith("openhands/") and data.base_url is None:
                data.base_url = "https://llm-proxy.app.all-hands.dev/"

            if should_set_litellm_extra_body(full_model, data.base_url):
                extra_kwargs["litellm_extra_body"] = {
                    "metadata": get_llm_metadata(
                        model_name=full_model, llm_type="agent"
                    )
                }

            llm = LLM(
                model=full_model,
                api_key=data.api_key_input,
                base_url=data.base_url,
                usage_id="agent",
                **extra_kwargs,
            )

        agent = existing_agent or get_default_cli_agent(llm=llm)
        agent = agent.model_copy(update={"llm": llm})

        # Handle condenser based on memory_condensation_enabled setting
        needs_condenser = data.memory_condensation_enabled or (
            agent.condenser and isinstance(agent.condenser, LLMSummarizingCondenser)
        )

        if needs_condenser:
            # Create condenser LLM - for ChatGPT subscription, use the same auth
            if data.is_chatgpt_subscription and chatgpt_auth is not None:
                model_name = str(data.model)
                condenser_llm = chatgpt_auth.create_llm(
                    model=model_name, usage_id="condenser"
                )
            else:
                condenser_llm = llm.model_copy(update={"usage_id": "condenser"})
                if should_set_litellm_extra_body(full_model, data.base_url):
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
                # Update existing condenser's LLM
                agent = agent.model_copy(
                    update={
                        "condenser": agent.condenser.model_copy(
                            update={"llm": condenser_llm}
                        )
                    }
                )
            elif data.memory_condensation_enabled and not agent.condenser:
                # Enable condensation with new condenser
                condenser = LLMSummarizingCondenser(llm=condenser_llm)
                agent = agent.model_copy(update={"condenser": condenser})

        if not data.memory_condensation_enabled and agent.condenser:
            # Disable condensation
            agent = agent.model_copy(update={"condenser": None})

        agent_store.save(agent)

        return SettingsSaveResult(success=True, error_message=None)
    except Exception as e:
        return SettingsSaveResult(success=False, error_message=str(e))
