"""Unit tests for the Databricks auth-method selector in the CLI settings.

Covers the behavioural layer only (``SettingsFormData.resolve_data_fields`` +
``_build_databricks_settings`` + ``save_settings``). The TUI widget-level
behaviour (show/hide of the conditional inputs) is covered by the snapshot
tests in ``test_settings_screen.py`` / ``test_settings_tab.py``.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

import openhands_cli.tui.modals.settings.utils as settings_utils
from openhands.sdk import LLM, Agent


@pytest.fixture
def fake_databricks_sdk(monkeypatch) -> MagicMock:
    """Make ``from databricks.sdk import WorkspaceClient`` succeed with a mock.

    Needed because the PROFILE auth path in the connector imports
    ``databricks.sdk`` lazily, and that package isn't pulled into the CLI's
    default venv. Tests that exercise profile auth through save_settings
    need this to avoid an ImportError during LLM construction.
    """
    mock_cls = MagicMock(name="WorkspaceClient")
    mock_instance = MagicMock(name="WorkspaceClient_instance")
    mock_instance.config.authenticate.return_value = {
        "Authorization": "Bearer mock-profile-token"
    }
    mock_cls.return_value = mock_instance

    sdk_mod = MagicMock(name="databricks.sdk")
    sdk_mod.WorkspaceClient = mock_cls
    monkeypatch.setitem(sys.modules, "databricks", MagicMock(name="databricks"))
    monkeypatch.setitem(sys.modules, "databricks.sdk", sdk_mod)
    return mock_cls


class FakeAgentStore:
    def __init__(self) -> None:
        self.saved_agents: list[Agent] = []

    def save(self, agent: Agent) -> None:
        self.saved_agents.append(agent)


@pytest.fixture
def deps(monkeypatch) -> FakeAgentStore:
    """Patch out persistence + defaults so we can drive save_settings end to end."""
    fake_store = FakeAgentStore()
    monkeypatch.setattr(settings_utils, "agent_store", fake_store)
    monkeypatch.setattr(
        settings_utils,
        "get_default_cli_agent",
        lambda llm: Agent(llm=llm),
    )
    monkeypatch.setattr(
        settings_utils,
        "should_set_litellm_extra_body",
        lambda model_name, base_url=None: False,
    )
    monkeypatch.setattr(
        settings_utils,
        "get_llm_metadata",
        lambda model_name, llm_type: {"model_name": model_name, "llm_type": llm_type},
    )
    return fake_store


# ---------------------------------------------------------------------------
# resolve_data_fields — defaults + validation
# ---------------------------------------------------------------------------


def test_resolve_defaults_to_pat_for_databricks() -> None:
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input="dapi-test",
        databricks_host="https://example.cloud.databricks.com",
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=None)

    assert data.databricks_auth_method == "pat"
    assert data.databricks_host == "https://example.cloud.databricks.com"


def test_resolve_clears_auth_method_for_non_databricks() -> None:
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="openai",
        model="gpt-4o",
        api_key_input="sk-123",
        databricks_auth_method="m2m",   # should be dropped
        databricks_client_id="client-id",
        databricks_client_secret_input="secret",
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=None)

    assert data.databricks_auth_method is None


def test_resolve_profile_method_defaults_profile_name() -> None:
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=None,
        databricks_auth_method="profile",
        databricks_host="https://example.cloud.databricks.com",
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=None)

    assert data.databricks_profile_name == "DEFAULT"
    # No API key required for profile auth
    assert data.api_key_input in (None, "")


def test_resolve_m2m_requires_client_id() -> None:
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=None,
        databricks_auth_method="m2m",
        databricks_client_id=None,
        databricks_client_secret_input="secret",
        databricks_host="https://example.cloud.databricks.com",
        memory_condensation_enabled=False,
    )
    with pytest.raises(Exception, match="Client ID is required"):
        data.resolve_data_fields(existing_agent=None)


def test_resolve_m2m_requires_client_secret() -> None:
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=None,
        databricks_auth_method="m2m",
        databricks_client_id="client-id",
        databricks_client_secret_input=None,
        databricks_host="https://example.cloud.databricks.com",
        memory_condensation_enabled=False,
    )
    with pytest.raises(Exception, match="Client Secret is required"):
        data.resolve_data_fields(existing_agent=None)


def test_resolve_m2m_reuses_existing_secret_when_blank() -> None:
    # We only need an object whose .llm.databricks_client_secret is a SecretStr.
    # A real DatabricksLLM triggers credential-resolution paths at construction
    # time that aren't relevant here, so a light stand-in is enough.
    existing_agent = SimpleNamespace(
        llm=SimpleNamespace(
            api_key=None,
            databricks_client_secret=SecretStr("existing-secret"),
            databricks_host="https://example.cloud.databricks.com",
            base_url=None,
        )
    )
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=None,
        databricks_auth_method="m2m",
        databricks_client_id="existing-client",
        databricks_client_secret_input=None,   # user left blank
        databricks_host="https://example.cloud.databricks.com",
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=existing_agent)

    assert data.databricks_client_secret_input == "existing-secret"


# ---------------------------------------------------------------------------
# Databricks host: required + fallbacks
# ---------------------------------------------------------------------------


def test_resolve_workspace_host_is_required() -> None:
    """Without any host (and no fallback), save must fail.

    The workspace host is the canonical Databricks URL — the SDK derives
    the AI Gateway base from it (``<host>/ai-gateway/<route>``) for every
    FM invocation. The AI Gateway host is an optional override; if
    neither is supplied there's nothing to route to.
    """
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input="dapi-test",
        databricks_auth_method="pat",
        databricks_host=None,
        databricks_ai_gateway_host=None,
        memory_condensation_enabled=False,
    )
    with pytest.raises(Exception, match="Workspace Host is required"):
        data.resolve_data_fields(existing_agent=None)


def test_resolve_pat_does_not_require_workspace_host() -> None:
    """PAT: filling only the AI Gateway host must succeed."""
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input="dapi-test",
        databricks_auth_method="pat",
        databricks_host=None,
        databricks_ai_gateway_host="https://gateway.example.com",
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=None)
    assert data.databricks_ai_gateway_host == "https://gateway.example.com"
    assert data.databricks_host in (None, "")


@pytest.mark.parametrize("method", ["m2m", "profile", "u2m"])
def test_resolve_oauth_methods_require_workspace_host(method: str) -> None:
    """OAuth-based auth must reject a missing workspace host."""
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=None,
        databricks_auth_method=method,  # type: ignore[arg-type]
        databricks_client_id="cid" if method == "m2m" else None,
        databricks_client_secret_input="shhh" if method == "m2m" else None,
        databricks_profile_name="DEFAULT" if method == "profile" else None,
        databricks_host=None,
        databricks_ai_gateway_host="https://gateway.example.com",
        memory_condensation_enabled=False,
    )
    with pytest.raises(Exception, match="Workspace Host is required"):
        data.resolve_data_fields(existing_agent=None)


def test_resolve_workspace_host_falls_back_to_base_url() -> None:
    """Advanced-mode users who only filled base_url should still pass.

    ``base_url`` becomes the workspace host; the AI Gateway host stays
    unset (the SDK will derive ``<host>/ai-gateway/<route>`` from the
    workspace URL automatically).
    """
    data = settings_utils.SettingsFormData(
        mode="advanced",
        custom_model="databricks/databricks-claude-sonnet-4-5",
        base_url="https://from-base-url.cloud.databricks.com",
        api_key_input="dapi-test",
        databricks_auth_method="pat",
        databricks_host=None,
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=None)
    assert (
        data.databricks_host == "https://from-base-url.cloud.databricks.com"
    )
    assert data.databricks_ai_gateway_host is None


def test_resolve_strips_ai_gateway_host_for_non_databricks() -> None:
    """Non-Databricks providers must not carry a stray gateway-host value."""
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="openai",
        model="gpt-4o",
        api_key_input="sk-xxx",
        databricks_ai_gateway_host="https://leftover.example.com",
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=None)
    assert data.databricks_ai_gateway_host is None


def test_build_settings_propagates_ai_gateway_host_when_set() -> None:
    """When the user provides a gateway host, it flows into the SDK kwargs."""
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input="dapi-xxx",
        databricks_auth_method="pat",
        databricks_host="https://adb.example.com",
        databricks_ai_gateway_host="https://gateway.example.com",
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=None)

    ns = settings_utils._build_databricks_settings(
        full_model=data.get_full_model_name(),
        data=data,
        api_key_val="dapi-xxx",
        timeout_val=None,
        max_in=None,
    )
    assert ns.databricks_host == "https://adb.example.com"
    assert ns.databricks_ai_gateway_host == "https://gateway.example.com"


def test_build_settings_leaves_ai_gateway_host_blank_for_single_url_workspaces() -> None:
    """Single-URL Databricks workspaces only need the workspace host.

    The SDK derives ``<host>/ai-gateway/<route>`` for every FM call from
    ``databricks_host`` itself, so the bridge intentionally leaves
    ``databricks_ai_gateway_host`` unset — that field is reserved for
    split deployments with a dedicated gateway hostname.
    """
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input="dapi-xxx",
        databricks_auth_method="pat",
        databricks_host="https://adb.example.com",
        databricks_ai_gateway_host=None,
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=None)

    ns = settings_utils._build_databricks_settings(
        full_model=data.get_full_model_name(),
        data=data,
        api_key_val="dapi-xxx",
        timeout_val=None,
        max_in=None,
    )
    assert ns.databricks_host == "https://adb.example.com"
    assert ns.databricks_ai_gateway_host is None
    assert ns.base_url == "https://adb.example.com"


def test_resolve_databricks_host_falls_back_to_existing_agent() -> None:
    """Editing other settings shouldn't force re-entering the host."""
    existing_agent = SimpleNamespace(
        llm=SimpleNamespace(
            api_key=None,
            databricks_host="https://existing.cloud.databricks.com",
            base_url=None,
            databricks_client_secret=None,
        )
    )
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input="dapi-test",
        databricks_auth_method="pat",
        databricks_host=None,
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=existing_agent)
    assert data.databricks_host == "https://existing.cloud.databricks.com"


# ---------------------------------------------------------------------------
# U2M (unified) auth method
# ---------------------------------------------------------------------------


def test_resolve_u2m_does_not_require_api_key_or_creds() -> None:
    """U2M relies on the SDK unified-auth chain; only host is needed."""
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=None,
        databricks_auth_method="u2m",
        databricks_host="https://example.cloud.databricks.com",
        memory_condensation_enabled=False,
    )
    # Should not raise — no API key, no client_id, no profile required.
    data.resolve_data_fields(existing_agent=None)
    assert data.databricks_auth_method == "u2m"
    assert data.api_key_input in (None, "")


def test_build_settings_u2m_passes_host_and_drops_creds() -> None:
    """U2M: host populated, every credential field cleared."""
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=None,
        databricks_auth_method="u2m",
        databricks_host="https://example.cloud.databricks.com",
        memory_condensation_enabled=False,
    )
    data.resolve_data_fields(existing_agent=None)

    ns = settings_utils._build_databricks_settings(
        full_model=data.get_full_model_name(),
        data=data,
        api_key_val=None,
        timeout_val=None,
        max_in=None,
    )
    assert ns.databricks_host == "https://example.cloud.databricks.com"
    assert ns.api_key is None
    assert ns.databricks_profile is None
    assert ns.databricks_client_id is None
    assert ns.databricks_client_secret is None


# ---------------------------------------------------------------------------
# _build_databricks_settings — per-method kwargs shape
# ---------------------------------------------------------------------------


def _base_form(method: str, **extra: Any) -> settings_utils.SettingsFormData:
    # Use advanced mode so ``base_url`` survives ``resolve_data_fields`` (basic
    # mode clears it). The dedicated ``databricks_host`` field is what the
    # bridge actually consumes; ``base_url`` here just verifies we don't
    # double-fill or accidentally drop it.
    data = settings_utils.SettingsFormData(
        mode="advanced",
        custom_model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=extra.pop("api_key_input", None),
        databricks_auth_method=method,  # type: ignore[arg-type]
        databricks_profile_name=extra.pop("databricks_profile_name", None),
        databricks_client_id=extra.pop("databricks_client_id", None),
        databricks_client_secret_input=extra.pop(
            "databricks_client_secret_input", None
        ),
        databricks_host=extra.pop(
            "databricks_host", "https://example.cloud.databricks.com"
        ),
        memory_condensation_enabled=False,
        base_url=extra.pop("base_url", "https://example.cloud.databricks.com"),
    )
    return data


def test_build_settings_pat_sets_api_key_only() -> None:
    data = _base_form("pat", api_key_input="dapi-xxx")
    ns = settings_utils._build_databricks_settings(
        full_model=data.get_full_model_name(),
        data=data,
        api_key_val="dapi-xxx",
        timeout_val=None,
        max_in=None,
    )
    assert isinstance(ns, SimpleNamespace)
    assert ns.api_key == "dapi-xxx"
    assert ns.databricks_profile is None
    assert ns.databricks_client_id is None
    assert ns.databricks_client_secret is None


def test_build_settings_profile_sets_profile_only() -> None:
    data = _base_form(
        "profile", databricks_profile_name="myprofile", api_key_input="should-be-dropped"
    )
    ns = settings_utils._build_databricks_settings(
        full_model=data.get_full_model_name(),
        data=data,
        api_key_val="should-be-dropped",
        timeout_val=None,
        max_in=None,
    )
    assert ns.databricks_profile == "myprofile"
    # API key is NOT passed when using profile auth — the bridge must not
    # accidentally send a stale PAT through with profile creds.
    assert ns.api_key is None
    assert ns.databricks_client_id is None
    assert ns.databricks_client_secret is None


def test_build_settings_m2m_sets_client_credentials_and_wraps_secret() -> None:
    data = _base_form(
        "m2m",
        databricks_client_id="cid",
        databricks_client_secret_input="shhh",
        api_key_input="also-dropped",
    )
    ns = settings_utils._build_databricks_settings(
        full_model=data.get_full_model_name(),
        data=data,
        api_key_val="also-dropped",
        timeout_val=None,
        max_in=None,
    )
    assert ns.databricks_client_id == "cid"
    assert isinstance(ns.databricks_client_secret, SecretStr)
    assert ns.databricks_client_secret.get_secret_value() == "shhh"
    assert ns.api_key is None
    assert ns.databricks_profile is None


# ---------------------------------------------------------------------------
# save_settings — end-to-end through kwargs_from_settings
# ---------------------------------------------------------------------------


def test_save_settings_pat_builds_llm_with_api_key(deps: FakeAgentStore) -> None:
    data = settings_utils.SettingsFormData(
        mode="advanced",
        custom_model="databricks/databricks-claude-sonnet-4-5",
        api_key_input="dapi-xxx",
        base_url="https://example.cloud.databricks.com",
        databricks_host="https://example.cloud.databricks.com",
        databricks_auth_method="pat",
        memory_condensation_enabled=False,
    )
    result = settings_utils.save_settings(data, existing_agent=None)
    assert result.success is True, result.error_message

    saved = deps.saved_agents[-1]
    api_key = saved.llm.api_key
    api_key_val = (
        api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
    )
    assert api_key_val == "dapi-xxx"
    assert saved.llm.databricks_profile is None
    assert saved.llm.databricks_client_id is None
    assert saved.llm.databricks_host == "https://example.cloud.databricks.com"


def test_save_settings_profile_builds_llm_with_profile(
    deps: FakeAgentStore, fake_databricks_sdk: MagicMock
) -> None:
    data = settings_utils.SettingsFormData(
        mode="advanced",
        custom_model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=None,
        base_url="https://example.cloud.databricks.com",
        databricks_host="https://example.cloud.databricks.com",
        databricks_auth_method="profile",
        databricks_profile_name="DEFAULT",
        memory_condensation_enabled=False,
    )
    result = settings_utils.save_settings(data, existing_agent=None)
    assert result.success is True, result.error_message

    saved = deps.saved_agents[-1]
    assert saved.llm.databricks_profile == "DEFAULT"
    assert saved.llm.api_key is None
    assert saved.llm.databricks_client_id is None
    assert saved.llm.databricks_host == "https://example.cloud.databricks.com"


def test_save_settings_m2m_builds_llm_with_client_credentials(
    deps: FakeAgentStore,
) -> None:
    data = settings_utils.SettingsFormData(
        mode="advanced",
        custom_model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=None,
        base_url="https://example.cloud.databricks.com",
        databricks_host="https://example.cloud.databricks.com",
        databricks_auth_method="m2m",
        databricks_client_id="cid",
        databricks_client_secret_input="shhh",
        memory_condensation_enabled=False,
    )
    result = settings_utils.save_settings(data, existing_agent=None)
    assert result.success is True, result.error_message

    saved = deps.saved_agents[-1]
    assert saved.llm.databricks_client_id == "cid"
    secret = saved.llm.databricks_client_secret
    assert isinstance(secret, SecretStr)
    assert secret.get_secret_value() == "shhh"
    assert saved.llm.api_key is None
    assert saved.llm.databricks_profile is None
    assert saved.llm.databricks_host == "https://example.cloud.databricks.com"


def test_save_settings_persists_ai_gateway_host(deps: FakeAgentStore) -> None:
    """Round-trip: form gateway host → DatabricksLLM.databricks_ai_gateway_host."""
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input="dapi-xxx",
        databricks_auth_method="pat",
        databricks_host="https://adb.example.com",
        databricks_ai_gateway_host="https://gateway.example.com",
        memory_condensation_enabled=False,
    )
    result = settings_utils.save_settings(data, existing_agent=None)
    assert result.success is True, result.error_message

    saved = deps.saved_agents[-1]
    assert saved.llm.databricks_host == "https://adb.example.com"
    assert saved.llm.databricks_ai_gateway_host == "https://gateway.example.com"


def test_save_settings_u2m_builds_llm_with_host_only(
    deps: FakeAgentStore, fake_databricks_sdk: MagicMock
) -> None:
    """U2M (unified): only host is set; SDK chain handles the rest at call time."""
    data = settings_utils.SettingsFormData(
        mode="basic",
        provider="databricks",
        model="databricks/databricks-claude-sonnet-4-5",
        api_key_input=None,
        databricks_host="https://example.cloud.databricks.com",
        databricks_auth_method="u2m",
        memory_condensation_enabled=False,
    )
    result = settings_utils.save_settings(data, existing_agent=None)
    assert result.success is True, result.error_message

    saved = deps.saved_agents[-1]
    assert saved.llm.databricks_host == "https://example.cloud.databricks.com"
    assert saved.llm.api_key is None
    assert saved.llm.databricks_profile is None
    assert saved.llm.databricks_client_id is None
