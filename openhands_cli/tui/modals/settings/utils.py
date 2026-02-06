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

    # New timeout field (seconds). Optional – if None the LLM default (300) is used.
    timeout: int | str | None = None
    max_tokens: int | str | None = None
    max_size: int | str | None = None
    # New max tokens field (optional). Maps to LLM max_output_tokens.
    # New max size for condenser (optional). Maps to LLMSummarizingCondenser max_size.

    # Whether the user wants memory condensation enabled
    memory_condensation_enabled: bool = True

    @field_validator("provider", "model", "custom_model", "base_url", "api_key_input")
    @classmethod
    def strip_strings(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    @field_validator("timeout", mode="before")
    @classmethod
    def validate_timeout(cls, v: str | int | None) -> int | None:
        """Validate and coerce the timeout value.

        Accepts an integer or a string containing digits. The value must be
        between 10 and 3600 seconds inclusive. Returns ``None`` for empty
        strings, ``None`` inputs, or values outside the allowed range. This
        allows the caller to retain the existing timeout when the user enters
        an invalid value.
        """
        if v is None:
            return None
        if isinstance(v, int):
            timeout_val = v
        elif isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
            if not v.isdigit():
                # Non‑numeric input – treat as invalid and ignore
                return None
            timeout_val = int(v)
        else:
            return None
        if not (10 <= timeout_val <= 3600):
            # Out‑of‑range – ignore and let caller keep original value
            return None
        return timeout_val

    @field_validator("max_tokens", mode="before")
    @classmethod
    def validate_max_tokens(cls, v: str | int | None) -> int | None:
        """Validate max_tokens input.

        Accepts an integer or numeric string. Returns ``None`` for empty or
        invalid values. No upper bound enforced (LLM may have its own limits).
        """
        if v is None:
            return None
        if isinstance(v, int):
            return v if v > 0 else None
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
            if not v.isdigit():
                return None
            val = int(v)
            return val if val > 0 else None
        return None

    @field_validator("max_size", mode="before")
    @classmethod
    def validate_max_size(cls, v: str | int | None) -> int | None:
        """Validate max_size for condenser.

        Must be a positive integer. Returns ``None`` for empty/invalid.
        """
        if v is None:
            return None
        if isinstance(v, int):
            return v if v > 0 else None
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
            if not v.isdigit():
                return None
            val = int(v)
            return val if val > 0 else None
        return None

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

        # Always add provider prefix - litellm requires it for routing.
        # Even if model contains '/' (e.g. "openai/gpt-4.1" from openrouter)
        # See: https://docs.litellm.ai/docs/providers
        return f"{self.provider}/{model_str}"


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

        if full_model.startswith("openhands/") and data.base_url is None:
            data.base_url = "https://llm-proxy.app.all-hands.dev/"

        if should_set_litellm_extra_body(full_model, data.base_url):
            extra_kwargs["litellm_extra_body"] = {
                "metadata": get_llm_metadata(model_name=full_model, llm_type="agent")
            }

        llm = LLM(
            model=full_model,
            api_key=data.api_key_input,
            base_url=data.base_url,
            usage_id="agent",
            timeout=int(data.timeout)
            if isinstance(data.timeout, str)
            else data.timeout,
            max_output_tokens=int(data.max_tokens)
            if isinstance(data.max_tokens, str)
            else data.max_tokens,
            **extra_kwargs,
        )

        agent = existing_agent or get_default_cli_agent(llm=llm)
        agent = agent.model_copy(update={"llm": llm})

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
            # Use provided max_size if available
            condenser = LLMSummarizingCondenser(
                llm=condenser_llm,
                max_size=int(data.max_size)
                if isinstance(data.max_size, str)
                else (data.max_size if data.max_size is not None else 240),
            )
            agent = agent.model_copy(update={"condenser": condenser})
        elif data.memory_condensation_enabled and agent.condenser:
            # Update existing condenser max_size if provided
            if (
                isinstance(agent.condenser, LLMSummarizingCondenser)
                and data.max_size is not None
            ):
                new_condenser = agent.condenser.model_copy(
                    update={
                        "max_size": int(data.max_size)
                        if isinstance(data.max_size, str)
                        else data.max_size
                    }
                )
                agent = agent.model_copy(update={"condenser": new_condenser})
        elif not data.memory_condensation_enabled and agent.condenser:
            # Disable condensation
            agent = agent.model_copy(update={"condenser": None})

        agent_store.save(agent)

        return SettingsSaveResult(success=True, error_message=None)
    except Exception as e:
        return SettingsSaveResult(success=False, error_message=str(e))
