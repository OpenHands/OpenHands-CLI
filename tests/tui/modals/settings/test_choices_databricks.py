"""Tests for CLI Databricks tier-2 dynamic picker in ``choices.get_model_options``."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from openhands_cli.tui.modals.settings import choices as choices_mod


@pytest.fixture(autouse=True)
def _clear_databricks_cache() -> None:
    """TTL cache is module-global — wipe between tests so they don't bleed."""
    choices_mod._databricks_cache.clear()
    yield
    choices_mod._databricks_cache.clear()


def _ep_entry(
    qualified_name: str,
    *,
    family: str = "anthropic",
    source: str = "curated+discovered",
    recommended: bool = False,
):
    """Build a minimal ``ModelPickerEntry``-shaped object for the SDK mock."""
    from openhands.sdk.llm.providers.databricks import ModelPickerEntry, ProviderFamily

    return ModelPickerEntry(
        qualified_name=qualified_name,
        name=qualified_name.split("/", 1)[1],
        family=ProviderFamily(family),
        source=source,
        endpoint_type="FOUNDATION_MODEL_API",
        ready=True,
        recommended=recommended,
    )


class TestDatabricksDynamicPicker:
    def test_non_databricks_provider_unaffected(self) -> None:
        """Non-databricks providers skip the dynamic codepath entirely."""
        with patch.object(choices_mod, "_get_databricks_model_options") as mock_dyn:
            options = choices_mod.get_model_options("openai")
        mock_dyn.assert_not_called()
        assert options   # non-empty static OpenAI list

    def test_dynamic_entries_are_used_when_available(self) -> None:
        """If ``_get_databricks_model_options`` returns entries, those win."""
        with patch.object(
            choices_mod,
            "_get_databricks_model_options",
            return_value=[
                ("databricks-claude-sonnet-4-5",
                 "databricks/databricks-claude-sonnet-4-5"),
                ("customer-private-gpt", "databricks/customer-private-gpt"),
            ],
        ):
            options = choices_mod.get_model_options("databricks")
        assert options == [
            ("databricks-claude-sonnet-4-5",
             "databricks/databricks-claude-sonnet-4-5"),
            ("customer-private-gpt", "databricks/customer-private-gpt"),
        ]

    def test_falls_back_to_static_when_dynamic_empty(self) -> None:
        """No creds / discovery failure → static VERIFIED + UNVERIFIED used as last resort."""
        with patch.object(
            choices_mod, "_get_databricks_model_options", return_value=[]
        ):
            options = choices_mod.get_model_options("databricks")

        assert options, "expected static fallback entries"
        # Short form (user-facing) never carries a "databricks/" prefix even
        # when the qualified id does.
        for short, _qualified in options:
            assert not short.startswith("databricks/")


class TestDatabricksResolveCredentials:
    """Credential resolution order: env > .databrickscfg profile > None."""

    def test_returns_none_when_sdk_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate ImportError on the SDK package.
        import builtins

        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name.startswith("openhands.sdk.llm.providers.databricks"):
                raise ImportError("no databricks extra")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _fake_import)
        assert choices_mod._resolve_databricks_credentials() is None

    def test_env_credentials_win(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "DATABRICKS_HOST", "https://my-workspace.cloud.databricks.com"
        )
        monkeypatch.setenv("DATABRICKS_TOKEN", "dapi-env-token")
        creds = choices_mod._resolve_databricks_credentials()
        assert creds is not None
        assert creds.host == "https://my-workspace.cloud.databricks.com"
        assert creds.get_token() == "dapi-env-token"

    def test_env_host_gets_https_prefix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Users often paste ``workspace.cloud.databricks.com`` — we must add https://."""
        monkeypatch.setenv("DATABRICKS_HOST", "my-workspace.cloud.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "dapi-env-token")
        creds = choices_mod._resolve_databricks_credentials()
        assert creds is not None
        assert creds.host == "https://my-workspace.cloud.databricks.com"


class TestDatabricksPickerIntegration:
    """End-to-end with ``get_picker_entries`` mocked.

    Note on patch target: ``choices.py`` imports ``get_picker_entries`` inside
    the function, via ``from openhands.sdk.llm.providers.databricks import …``.
    That means the name is looked up as an attribute of the *package* on each
    call, so we must patch
    ``openhands.sdk.llm.providers.databricks.get_picker_entries`` (not
    ``discovery.get_picker_entries``, which is a different binding).
    """

    _PATCH_TARGET = "openhands.sdk.llm.providers.databricks.get_picker_entries"

    def test_picker_entries_become_tuples(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DATABRICKS_HOST", "https://ws.cloud.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "tok")

        entries = [
            _ep_entry(
                "databricks/databricks-claude-sonnet-4-5",
                recommended=True,
            ),
            _ep_entry(
                "databricks/databricks-gemini-2-5-flash",
                family="gemini",
                source="discovered",
            ),
        ]
        with patch(self._PATCH_TARGET, return_value=entries):
            options = choices_mod._get_databricks_model_options()

        assert options == [
            (
                "databricks-claude-sonnet-4-5",
                "databricks/databricks-claude-sonnet-4-5",
            ),
            (
                "databricks-gemini-2-5-flash",
                "databricks/databricks-gemini-2-5-flash",
            ),
        ]

    def test_cache_hit_skips_second_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DATABRICKS_HOST", "https://ws.cloud.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "tok")

        entries = [_ep_entry("databricks/databricks-claude-sonnet-4-5")]
        with patch(self._PATCH_TARGET, return_value=entries) as mock_fn:
            choices_mod._get_databricks_model_options()
            choices_mod._get_databricks_model_options()
        assert mock_fn.call_count == 1

    def test_discovery_exception_degrades_to_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DATABRICKS_HOST", "https://ws.cloud.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "tok")

        with patch(self._PATCH_TARGET, side_effect=RuntimeError("boom")):
            options = choices_mod._get_databricks_model_options()
        assert options == []

    def test_no_creds_still_returns_curated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without env/profile creds we still get the curated entries.

        We stub the credential resolver so the test doesn't depend on whether
        ``~/.databrickscfg`` happens to be populated on the dev machine.
        """
        monkeypatch.delenv("DATABRICKS_HOST", raising=False)
        monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
        monkeypatch.delenv("DATABRICKS_ACCESS_TOKEN", raising=False)
        with patch.object(
            choices_mod, "_resolve_databricks_credentials", return_value=None
        ):
            options = choices_mod._get_databricks_model_options()
        assert options, "expected curated entries even without credentials"
        # Should contain exactly the curated tier (8 entries).
        from openhands.sdk.llm.providers.databricks import CURATED_DATABRICKS_MODELS

        assert len(options) == len(CURATED_DATABRICKS_MODELS)
        for _, qualified in options:
            assert qualified.startswith("databricks/")
