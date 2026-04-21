from types import SimpleNamespace
from typing import Any, Literal

from pydantic import BaseModel, SecretStr, field_validator

from openhands.sdk import LLM, Agent, LLMSummarizingCondenser, create_llm
from openhands.sdk.llm.providers.databricks.settings_bridge import (
    kwargs_from_settings,
)
from openhands_cli.stores import AgentStore
from openhands_cli.utils import (
    get_default_cli_agent,
    get_llm_metadata,
    should_set_litellm_extra_body,
)


agent_store = AgentStore()


DatabricksAuthMethod = Literal["pat", "m2m", "profile", "u2m"]
"""Auth strategies surfaced in the CLI settings TUI.

Maps to the SDK's ``AuthStrategy`` enum as follows:

- ``pat``     → SDK PAT (Personal Access Token via ``api_key``)
- ``m2m``     → SDK M2M (service-principal client_id + client_secret)
- ``profile`` → SDK PROFILE (named ``[profile]`` in ``~/.databrickscfg``)
- ``u2m``     → SDK UNIFIED (relies on the databricks-sdk auth chain;
                 picks up cached browser-OAuth tokens written by
                 ``databricks auth login``). The CLI itself does NOT run an
                 inline browser PKCE flow — that's web-only — so "U2M" here
                 is shorthand for "log in once with the Databricks CLI,
                 then this option uses those creds for every call."

Both ``profile`` and ``u2m`` require the optional ``databricks-sdk`` package
to be installed in the same venv as the CLI; the connector raises a clear
ImportError if it's missing.
"""


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

    # Databricks auth strategy (only meaningful when the selected model is a
    # databricks/* model). See ``DatabricksAuthMethod`` above for what each
    # value maps to in the SDK.
    databricks_auth_method: DatabricksAuthMethod | None = None
    databricks_profile_name: str | None = None
    databricks_client_id: str | None = None
    databricks_client_secret_input: str | None = None
    # Databricks workspace URL (e.g. ``https://adb-123.cloud.databricks.com``).
    # Canonical, required field. Used for:
    #   * FM invocations (the SDK derives ``<host>/ai-gateway/<route>`` from
    #     this for every Foundation Model call) — unless overridden by
    #     ``databricks_ai_gateway_host``.
    #   * Auth/token resolution (OAuth flows mint tokens here).
    #   * Discovery and the opt-in metadata probe (``/api/2.0/*``).
    # Required for OAuth-based methods (m2m / profile / u2m). For PAT it's
    # only optional when ``databricks_ai_gateway_host`` is also supplied.
    databricks_host: str | None = None

    # Optional AI Gateway override (scheme + hostname only, no path).
    # Use this for split deployments where the gateway has a dedicated
    # hostname (e.g. ``https://<workspace_id>.ai-gateway.cloud.databricks.com``).
    # When set, every FM invocation routes here directly. Discovery,
    # metadata probes, and OAuth still go to ``databricks_host``.
    # Leave blank for the typical single-URL Databricks workspace.
    databricks_ai_gateway_host: str | None = None

    # New timeout field (seconds). Optional – if None the LLM default (300) is used.
    timeout: int | str | None = None
    max_tokens: int | str | None = None
    max_size: int | str | None = None
    # New max tokens field (optional). Maps to LLM max_input_tokens.
    # New max size for condenser (optional). Maps to LLMSummarizingCondenser max_size.

    # Whether the user wants memory condensation enabled
    memory_condensation_enabled: bool = True

    @field_validator(
        "provider",
        "model",
        "custom_model",
        "base_url",
        "api_key_input",
        "databricks_profile_name",
        "databricks_client_id",
        "databricks_client_secret_input",
        "databricks_host",
        "databricks_ai_gateway_host",
    )
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
            return v if v > 30 else None
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
            if not v.isdigit():
                return None
            val = int(v)
            return val if val > 30 else None
        return None

    def resolve_data_fields(self, existing_agent: Agent | None) -> None:
        is_databricks_adv = False
        # Check advance mode requirements
        if self.mode == "advanced":
            if not self.custom_model:
                raise Exception("Custom model is required in advanced mode")
            is_databricks_adv = self.custom_model.startswith("databricks/")
            if not self.base_url and not is_databricks_adv:
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

        is_databricks_basic = (
            self.mode == "basic" and (self.provider or "") == "databricks"
        )
        is_databricks = is_databricks_basic or is_databricks_adv

        # Default auth method for Databricks is PAT; ignore the field for
        # non-Databricks providers so it doesn't leak into non-db code paths.
        if not is_databricks:
            self.databricks_auth_method = None
            self.databricks_host = None
            self.databricks_ai_gateway_host = None
        elif self.databricks_auth_method is None:
            self.databricks_auth_method = "pat"

        # Workspace host is the canonical, required URL. The SDK derives the
        # AI Gateway base from it (``<host>/ai-gateway/<route>``) for every
        # FM invocation; OAuth methods mint tokens against it; metadata
        # probes hit it. Fall back to ``base_url`` (advanced mode) and then
        # the prior agent's value so editing other settings doesn't force
        # re-entry.
        if is_databricks:
            if not self.databricks_host:
                self.databricks_host = self.base_url
            if not self.databricks_host and existing_agent is not None:
                self.databricks_host = getattr(
                    existing_agent.llm, "databricks_host", None
                ) or getattr(existing_agent.llm, "base_url", None)
            # PAT users with a dedicated gateway can skip the workspace URL
            # if they explicitly provided a gateway host; everyone else
            # needs the workspace host.
            if not self.databricks_host and not self.databricks_ai_gateway_host:
                raise Exception(
                    "Databricks Workspace Host is required (e.g., "
                    "https://adb-1234.cloud.databricks.com)"
                )
            if not self.databricks_host and self.databricks_auth_method in (
                "m2m",
                "profile",
                "u2m",
            ):
                raise Exception(
                    "Databricks Workspace Host is required for "
                    f"{self.databricks_auth_method.upper()} auth (e.g., "
                    "https://adb-1234.cloud.databricks.com)"
                )

        # AI Gateway host is an OPTIONAL override. Carry it over from the
        # prior agent only if explicitly set there — never auto-default it
        # from the workspace host (the SDK does that itself).
        if is_databricks:
            if not self.databricks_ai_gateway_host and existing_agent is not None:
                self.databricks_ai_gateway_host = getattr(
                    existing_agent.llm, "databricks_ai_gateway_host", None
                )

        # Normalise the Databricks profile name — empty → DEFAULT.
        if is_databricks and self.databricks_auth_method == "profile":
            if not self.databricks_profile_name:
                self.databricks_profile_name = "DEFAULT"

        # M2M needs both halves of the client credential.
        if is_databricks and self.databricks_auth_method == "m2m":
            if not self.databricks_client_id:
                raise Exception(
                    "Databricks Client ID is required for service-principal (M2M) auth"
                )
            # Client secret can be kept from existing agent if not re-entered.
            if not self.databricks_client_secret_input and existing_agent:
                existing = getattr(existing_agent.llm, "databricks_client_secret", None)
                if isinstance(existing, SecretStr):
                    self.databricks_client_secret_input = existing.get_secret_value()
                elif isinstance(existing, str):
                    self.databricks_client_secret_input = existing
            if not self.databricks_client_secret_input:
                raise Exception(
                    "Databricks Client Secret is required for service-principal "
                    "(M2M) auth"
                )

        # PAT / non-databricks: API key is required. For PROFILE, M2M, and
        # U2M (unified chain) the api_key field isn't used by the connector,
        # so we skip the check.
        needs_api_key = not (
            is_databricks and self.databricks_auth_method in ("profile", "m2m", "u2m")
        )

        if needs_api_key:
            if not self.api_key_input and existing_agent:
                existing_llm_api_key = existing_agent.llm.api_key
                existing_llm_api_key = (
                    existing_llm_api_key.get_secret_value()
                    if isinstance(existing_llm_api_key, SecretStr)
                    else existing_llm_api_key
                )
                self.api_key_input = existing_llm_api_key

            # Databricks PAT is optional at construction (host alone is enough
            # for metadata-only operations); only the true non-databricks
            # providers must have an API key up front.
            if not self.api_key_input and not is_databricks:
                raise Exception("API Key is required")

    def get_full_model_name(self) -> str:
        if self.mode == "advanced":
            return str(self.custom_model)

        model_str = str(self.model)
        if self.provider == "databricks":
            # Model select stores full FMAPI id (e.g. databricks/databricks-meta-...).
            return model_str

        # Always add provider prefix - litellm requires it for routing.
        # Even if model contains '/' (e.g. "openai/gpt-4.1" from openrouter)
        # See: https://docs.litellm.ai/docs/providers
        return f"{self.provider}/{model_str}"


class SettingsSaveResult(BaseModel):
    """Result of attempting to save settings."""

    success: bool
    error_message: str | None = None


def _build_databricks_settings(
    *,
    full_model: str,
    data: SettingsFormData,
    api_key_val: str | None,
    timeout_val: int | None,
    max_in: int | None,
) -> SimpleNamespace:
    """Assemble the Databricks-specific ``SimpleNamespace`` consumed by the
    ``kwargs_from_settings`` bridge.

    Centralised in one place so the agent-LLM and condenser-LLM call sites
    stay in sync and only one place needs updating when the bridge grows a
    new field. The returned namespace always carries the fields for the
    currently selected auth method and leaves the unused ones as ``None``
    so the bridge drops them.
    """
    auth_method = data.databricks_auth_method or "pat"
    # ``resolve_data_fields`` guarantees ``databricks_host`` is set (or, for
    # PAT-only flows, ``databricks_ai_gateway_host`` is set as the override).
    workspace_host = data.databricks_host or None
    ai_gateway_host = data.databricks_ai_gateway_host or None

    ns = SimpleNamespace(
        model=full_model,
        api_key=api_key_val if (auth_method == "pat" and api_key_val) else None,
        # ``base_url`` mirrors the workspace URL so any generic LLM-metadata
        # logging still has a URL to surface. The SDK ignores it for FM
        # routing — that's driven by ``databricks_host`` (default) or
        # ``databricks_ai_gateway_host`` (override).
        base_url=workspace_host or ai_gateway_host,
        databricks_host=workspace_host,
        databricks_ai_gateway_host=ai_gateway_host,
        databricks_profile=(
            data.databricks_profile_name if auth_method == "profile" else None
        ),
        databricks_client_id=(
            data.databricks_client_id if auth_method == "m2m" else None
        ),
        databricks_client_secret=(
            SecretStr(data.databricks_client_secret_input)
            if auth_method == "m2m" and data.databricks_client_secret_input
            else None
        ),
        timeout=timeout_val,
        max_input_tokens=max_in,
    )
    # ``u2m`` deliberately leaves api_key / profile / client_id / secret as
    # None so the SDK's UNIFIED auth chain (``databricks-sdk``) is the only
    # remaining path — it picks up whatever ``databricks auth login`` cached
    # for this host. No extra namespace fields needed for that path.
    return ns


def save_settings(
    data: SettingsFormData, existing_agent: Agent | None
) -> SettingsSaveResult:
    try:
        data.resolve_data_fields(existing_agent)
        extra_kwargs: dict[str, Any] = {}

        full_model = data.get_full_model_name()

        if full_model.startswith("openhands/") and data.base_url is None:
            data.base_url = "https://llm-proxy.app.all-hands.dev/"

        max_input_tokens = (
            int(data.max_tokens)
            if isinstance(data.max_tokens, str)
            else data.max_tokens
        )

        if should_set_litellm_extra_body(full_model, data.base_url):
            extra_kwargs["litellm_extra_body"] = {
                "metadata": get_llm_metadata(model_name=full_model, llm_type="agent")
            }

        api_key_val = data.api_key_input or None
        timeout_val = (
            int(data.timeout) if isinstance(data.timeout, str) else data.timeout
        )
        max_in = (
            int(data.max_tokens)
            if isinstance(data.max_tokens, str)
            else data.max_tokens
        )

        if full_model.startswith("databricks/"):
            db_settings = _build_databricks_settings(
                full_model=full_model,
                data=data,
                api_key_val=api_key_val,
                timeout_val=timeout_val,
                max_in=max_in,
            )
            llm = create_llm(**kwargs_from_settings(db_settings, usage_id="agent"))
            condenser_llm = create_llm(
                **kwargs_from_settings(db_settings, usage_id="condenser")
            )
        else:
            llm = LLM(
                model=full_model,
                api_key=api_key_val,
                base_url=data.base_url,
                usage_id="agent",
                timeout=timeout_val,
                max_input_tokens=max_in,
                **extra_kwargs,
            )

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

        agent = existing_agent or get_default_cli_agent(llm=llm)
        agent = agent.model_copy(update={"llm": llm})

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
            if full_model.startswith("databricks/"):
                db_settings = _build_databricks_settings(
                    full_model=full_model,
                    data=data,
                    api_key_val=api_key_val,
                    timeout_val=timeout_val,
                    max_in=max_in,
                )
                condenser_llm = create_llm(
                    **kwargs_from_settings(db_settings, usage_id="condenser")
                )
            else:
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
