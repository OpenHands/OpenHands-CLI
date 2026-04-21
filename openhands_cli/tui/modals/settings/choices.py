import logging
import os
import time

import litellm

from openhands.sdk.llm import UNVERIFIED_MODELS_EXCLUDING_BEDROCK, VERIFIED_MODELS


logger = logging.getLogger(__name__)

# Get set of valid litellm provider names for filtering
# See: https://docs.litellm.ai/docs/providers
_VALID_LITELLM_PROVIDERS: set[str] = {
    str(getattr(p, "value", p)) for p in litellm.provider_list
}


# ---------------------------------------------------------------------------
# Databricks AI-Gateway model discovery (tier-2 dynamic picker)
# ---------------------------------------------------------------------------
#
# When the user selects provider=``databricks`` in the settings TUI we want to
# surface the live workspace endpoints (FOUNDATION_MODEL_API + EXTERNAL_MODEL)
# alongside the curated Claude/GPT/Gemini defaults — same two-tier model picker
# as the web UI. Implementation details:
#
# * Resolution order for credentials mirrors the web route + DatabricksLLM:
#     1. env: DATABRICKS_HOST + (DATABRICKS_TOKEN | DATABRICKS_ACCESS_TOKEN)
#     2. ~/.databrickscfg DEFAULT profile (via the databricks SDK) — only
#        attempted if the SDK is installed and env didn't already resolve.
# * Any failure (SDK missing, profile unreadable, workspace unreachable,
#   401/403) degrades silently to curated-only — the static ``VERIFIED_MODELS``
#   entries are always returned so the CLI stays usable offline.
# * TTL cache keyed on host keeps this O(1) across rapid provider switches
#   within a single TUI session.

_DATABRICKS_CACHE_TTL_S = 300
_databricks_cache: dict[str, tuple[float, list[tuple[str, str]]]] = {}


def _resolve_databricks_credentials():
    """Best-effort credential resolution for dynamic discovery. Returns None on failure.

    Import-local so this module stays importable when the ``databricks`` extra
    isn't installed (pure LiteLLM users).
    """
    try:
        from openhands.sdk.llm.providers.databricks import (
            AuthStrategy,
            DatabricksCredentials,
        )
    except ImportError:
        return None

    host = os.environ.get("DATABRICKS_HOST", "").strip().rstrip("/")
    token = (
        os.environ.get("DATABRICKS_TOKEN", "").strip()
        or os.environ.get("DATABRICKS_ACCESS_TOKEN", "").strip()
    )

    if host and token:
        if not (host.startswith("http://") or host.startswith("https://")):
            host = f"https://{host}"
        try:
            return DatabricksCredentials(
                host=host,
                get_token=lambda t=token: t,
                auth_method=AuthStrategy.PAT,
            )
        except Exception as exc:
            logger.debug("databricks_env_cred_build_failed: %s", exc)

    # Fall back to ~/.databrickscfg DEFAULT via the databricks SDK.
    try:
        from databricks.sdk.core import Config as _DbxConfig  # type: ignore
    except ImportError:
        return None

    try:
        cfg = _DbxConfig(profile="DEFAULT")
        cfg_host = (cfg.host or "").strip().rstrip("/")
        if not cfg_host:
            return None
        if not (cfg_host.startswith("http://") or cfg_host.startswith("https://")):
            cfg_host = f"https://{cfg_host}"
        # databricks-sdk Config.authenticate() returns a headers dict with
        # ``Authorization: Bearer …``; extract the bearer for our simple probe.
        headers = cfg.authenticate() or {}
        auth = headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        cfg_token = auth.split(" ", 1)[1]
        return DatabricksCredentials(
            host=cfg_host,
            get_token=lambda t=cfg_token: t,
            auth_method=AuthStrategy.PROFILE,
        )
    except Exception as exc:
        logger.debug("databricks_profile_cred_build_failed: %s", exc)
        return None


def _resolve_credentials_for_host(host: str, auth_method: str, **kwargs) -> "DatabricksCredentials | None":  # type: ignore[name-defined]  # noqa: F821
    """Build credentials from the current form state for a specific host.

    Used when the user has already filled in the host (and possibly auth
    method) so we can discover models for *that* workspace rather than the
    DEFAULT profile workspace.

    ``auth_method`` is one of ``"pat"``, ``"m2m"``, ``"profile"``, ``"u2m"``.
    Extra kwargs carry method-specific values (``api_key``, ``profile``).
    """
    try:
        from openhands.sdk.llm.providers.databricks import (
            AuthStrategy,
            DatabricksCredentials,
        )
    except ImportError:
        return None

    host = host.strip().rstrip("/")
    if not host.startswith("https://"):
        host = f"https://{host}"

    if auth_method == "pat":
        api_key = kwargs.get("api_key", "")
        if not api_key:
            return None
        return DatabricksCredentials(
            host=host, get_token=lambda t=api_key: t, auth_method=AuthStrategy.PAT
        )

    if auth_method in ("u2m", "profile"):
        profile = kwargs.get("profile", "DEFAULT") if auth_method == "profile" else None
        try:
            from databricks.sdk.core import Config as _DbxConfig  # type: ignore
            cfg = _DbxConfig(host=host, **({"profile": profile} if profile else {}))
            headers = cfg.authenticate() or {}
            auth_header = headers.get("Authorization", "")
            if not auth_header.lower().startswith("bearer "):
                return None
            token = auth_header.split(" ", 1)[1]
            return DatabricksCredentials(
                host=host,
                get_token=lambda t=token: t,
                auth_method=AuthStrategy.PROFILE if auth_method == "profile" else AuthStrategy.U2M,
            )
        except Exception as exc:
            logger.debug("databricks_host_cred_build_failed host=%s: %s", host, exc)
            return None

    # M2M: requires client_id + client_secret — skip discovery silently
    return None


def _get_databricks_model_options(
    credentials: "DatabricksCredentials | None" = None,  # type: ignore[name-defined]  # noqa: F821
) -> list[tuple[str, str]]:
    """Return merged curated + discovered model options for the picker.

    Output format matches the rest of ``get_model_options`` — ``(short,
    qualified)`` tuples where ``short`` is the bare endpoint name (what the
    user sees) and ``qualified`` is ``"databricks/<name>"`` (what's written
    to settings). Recommended curated picks sort first; the rest are sorted
    by family then name — identical order to the web picker.

    If ``credentials`` is supplied (e.g. resolved from the current form state
    when the user changes auth method or host) it takes priority over the
    auto-resolved DEFAULT profile credentials. This lets U2M / profile auth
    immediately show the full model list for the *typed* workspace host.
    """
    try:
        from openhands.sdk.llm.providers.databricks import get_picker_entries
    except ImportError:
        return []

    if credentials is None:
        credentials = _resolve_databricks_credentials()
    cache_key = credentials.host if credentials is not None else "__curated_only__"

    now = time.time()
    cached = _databricks_cache.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]

    try:
        entries = get_picker_entries(credentials=credentials)
    except Exception as exc:
        logger.debug("databricks_picker_failed: %s", exc)
        entries = []

    options: list[tuple[str, str]] = []
    for e in entries:
        short = (
            e.qualified_name[len("databricks/") :]
            if e.qualified_name.startswith("databricks/")
            else e.name
        )
        options.append((short, e.qualified_name))

    _databricks_cache[cache_key] = (now + _DATABRICKS_CACHE_TTL_S, options)
    return options


def get_provider_options() -> list[tuple[str, str]]:
    """Get list of available LLM providers.

    Includes:
    - All VERIFIED_MODELS providers (openhands, openai, anthropic, mistral)
      even if not in litellm.provider_list (e.g. 'openhands' is custom)
    - UNVERIFIED providers that are known to litellm (filters out invalid
      "providers" like 'meta-llama', 'Qwen' which are vendor names)

    'openhands' is always listed first; remaining providers are sorted
    alphabetically.
    """
    # Verified providers always included (includes custom like 'openhands')
    verified_providers = set(VERIFIED_MODELS.keys())

    # Unverified providers are filtered to only valid litellm providers
    unverified_providers = set(UNVERIFIED_MODELS_EXCLUDING_BEDROCK.keys())
    valid_unverified = unverified_providers & _VALID_LITELLM_PROVIDERS

    # Combine and sort alphabetically, then pin 'openhands' to the top
    all_valid_providers = sorted(verified_providers | valid_unverified)
    if "openhands" in all_valid_providers:
        all_valid_providers.remove("openhands")
        all_valid_providers.insert(0, "openhands")

    return [(provider, provider) for provider in all_valid_providers]


def get_model_options(provider: str, credentials=None) -> list[tuple[str, str]]:
    """Get list of available models for a provider.

    For most providers, returns the static VERIFIED + UNVERIFIED union (original
    order preserved, duplicates removed).

    For ``databricks``, returns the **two-tier picker** (curated + live-discovered
    AI Gateway endpoints). Falls back to the static ``VERIFIED_MODELS["databricks"]``
    list if credentials aren't available or discovery fails — the picker is
    never empty.
    """
    if provider == "databricks":
        dynamic = _get_databricks_model_options(credentials=credentials)
        if dynamic:
            return dynamic
        # Fall through to the static list below as a last-resort curated view.

    models = VERIFIED_MODELS.get(
        provider, []
    ) + UNVERIFIED_MODELS_EXCLUDING_BEDROCK.get(provider, [])

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_models: list[str] = []
    for model in models:
        if model not in seen:
            seen.add(model)
            unique_models.append(model)

    result: list[tuple[str, str]] = []
    for model in unique_models:
        if provider == "databricks" and model.startswith("databricks/"):
            short = model.removeprefix("databricks/")
            result.append((short, model))
        else:
            result.append((model, model))
    return result


provider_options = get_provider_options()
