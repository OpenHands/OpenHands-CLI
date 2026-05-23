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


DatabricksAuthMethod = Literal["m2m", "u2m"]
"""Auth strategies surfaced in the CLI settings TUI.

Maps to the SDK's ``AuthStrategy`` enum as follows:

- ``m2m``     → SDK M2M (service-principal client_id + client_secret)
- ``u2m``     → Browser OAuth PKCE flow with a custom OAuth App.
                 The CLI runs an inline PKCE flow and stores the token as
                 ``stored_u2m_tokens``. The user authenticates once; the
                 refresh_token is used to renew access automatically.

                 Previously supported but removed: ``pat`` (Personal Access
                 Token) and ``profile`` (~/.databrickscfg) — use M2M or U2M.
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
    databricks_client_id: str | None = None
    databricks_client_secret_input: str | None = None
    # U2M OAuth app credentials (separate from M2M service principal)
    databricks_u2m_client_id: str | None = None
    databricks_u2m_client_secret_input: str | None = None
    # Optional redirect URI — defaults to http://localhost:8080/callback
    databricks_u2m_redirect_uri: str | None = None
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
        "databricks_client_id",
        "databricks_client_secret_input",
        "databricks_u2m_client_id",
        "databricks_u2m_client_secret_input",
        "databricks_u2m_redirect_uri",
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

        # Default auth method for Databricks is U2M; ignore the field for
        # non-Databricks providers so it doesn't leak into non-db code paths.
        if not is_databricks:
            self.databricks_auth_method = None
            self.databricks_host = None
            self.databricks_ai_gateway_host = None
        elif self.databricks_auth_method is None:
            self.databricks_auth_method = "u2m"

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
            if not self.databricks_host:
                raise Exception(
                    "Databricks Workspace Host is required (e.g., "
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

        # U2M: carry credentials from the existing agent if not re-entered.
        # All three fields (client_id, redirect_uri, client_secret) are optional,
        # so no error if absent — public PKCE apps omit client_secret entirely.
        if is_databricks and self.databricks_auth_method == "u2m" and existing_agent:
            if not self.databricks_u2m_client_id:
                existing_id = getattr(
                    existing_agent.llm, "databricks_u2m_client_id", None
                )
                if existing_id:
                    self.databricks_u2m_client_id = existing_id

            if not self.databricks_u2m_redirect_uri:
                existing_uri = getattr(
                    existing_agent.llm, "databricks_u2m_redirect_uri", None
                )
                if existing_uri:
                    self.databricks_u2m_redirect_uri = existing_uri

            if not self.databricks_u2m_client_secret_input:
                existing = getattr(
                    existing_agent.llm, "databricks_u2m_client_secret", None
                )
                if isinstance(existing, SecretStr):
                    self.databricks_u2m_client_secret_input = existing.get_secret_value()
                elif isinstance(existing, str):
                    self.databricks_u2m_client_secret_input = existing

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
    existing_agent: "Agent | None" = None,
) -> SimpleNamespace:
    """Assemble the Databricks-specific ``SimpleNamespace`` consumed by the
    ``kwargs_from_settings`` bridge.

    Centralised in one place so the agent-LLM and condenser-LLM call sites
    stay in sync and only one place needs updating when the bridge grows a
    new field. The returned namespace always carries the fields for the
    currently selected auth method and leaves the unused ones as ``None``
    so the bridge drops them.

    ``existing_agent`` is used to carry forward auth state that lives
    outside the visible form fields:
    - ``stored_u2m_tokens`` — U2M session survives a model switch so the
      user doesn't need to re-authenticate just because they picked a
      different model.
    """
    auth_method = data.databricks_auth_method or "pat"
    # ``resolve_data_fields`` guarantees ``databricks_host`` is set (or, for
    # PAT-only flows, ``databricks_ai_gateway_host`` is set as the override).
    workspace_host = data.databricks_host or None
    ai_gateway_host = data.databricks_ai_gateway_host or None

    # Carry U2M session tokens forward when the user only changed the model.
    # The PKCE flow in settings_screen.py bypasses save_settings entirely and
    # writes tokens directly, so this path never overwrites a fresh token.
    existing_u2m_tokens = None
    if auth_method == "u2m" and existing_agent is not None:
        existing_u2m_tokens = getattr(existing_agent.llm, "stored_u2m_tokens", None)

    ns = SimpleNamespace(
        model=full_model,
        # Neither U2M nor M2M use the generic api_key field.
        api_key=None,
        base_url=workspace_host or ai_gateway_host,
        databricks_host=workspace_host,
        databricks_ai_gateway_host=ai_gateway_host,
        databricks_client_id=(
            data.databricks_client_id if auth_method == "m2m" else None
        ),
        databricks_client_secret=(
            SecretStr(data.databricks_client_secret_input)
            if auth_method == "m2m" and data.databricks_client_secret_input
            else None
        ),
        databricks_u2m_client_id=(
            data.databricks_u2m_client_id if auth_method == "u2m" else None
        ),
        databricks_u2m_client_secret=(
            SecretStr(data.databricks_u2m_client_secret_input)
            if auth_method == "u2m" and data.databricks_u2m_client_secret_input
            else None
        ),
        databricks_u2m_redirect_uri=(
            data.databricks_u2m_redirect_uri if auth_method == "u2m" else None
        ),
        # Carry the existing U2M session forward — avoids re-auth on model switch.
        stored_u2m_tokens=existing_u2m_tokens,
        # Use the metadata probe so the client gets authoritative api_types
        # from /api/2.0/serving-endpoints/{name} instead of name-pattern guessing.
        databricks_metadata_probe=True,
        timeout=timeout_val,
        max_input_tokens=max_in,
    )
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
                existing_agent=existing_agent,
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
                    existing_agent=existing_agent,
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
