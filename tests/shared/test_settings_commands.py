"""Tests for schema-driven settings slash command helpers."""

from typing import cast

import pytest
from pydantic import SecretStr

from openhands_cli.shared.settings_commands import (
    format_setting_argument_hint,
    get_programmatic_setting_command_map,
    handle_programmatic_setting_command,
)
from openhands_cli.stores.agent_store import AgentStore
from openhands_cli.stores.programmatic_settings import CliProgrammaticSettings


def _make_store(monkeypatch: pytest.MonkeyPatch, tmp_path) -> AgentStore:
    monkeypatch.setenv("OPENHANDS_PERSISTENCE_DIR", str(tmp_path))
    return AgentStore()


class TestFormatSettingArgumentHint:
    """Tests for slash-command argument hint formatting."""

    @pytest.mark.parametrize(
        ("command", "separator", "expected"),
        [
            ("critic", "|", "on|off"),
            ("critic", " | ", "on | off"),
            ("issue-threshold", "|", "<number>"),
            ("llm-api-key", "|", "<secret>"),
            ("llm-model", "|", "<value>"),
        ],
    )
    def test_formats_expected_hints(
        self,
        command: str,
        separator: str,
        expected: str,
    ) -> None:
        """Hints should stay consistent anywhere settings commands are surfaced."""
        field = get_programmatic_setting_command_map()[command]

        assert format_setting_argument_hint(field, separator=separator) == expected


class TestHandleProgrammaticSettingCommand:
    """Tests for schema-driven settings slash command handling."""

    def test_returns_none_for_unknown_command(self) -> None:
        """Unknown commands should fall through so other handlers can process them."""
        assert handle_programmatic_setting_command("does-not-exist", "value") is None

    @pytest.mark.parametrize(
        ("command", "argument", "message"),
        [
            ("critic", "maybe", "Expected one of:"),
            ("critic-mode", "sometimes", "Expected one of:"),
            (
                "max-refinement-iterations",
                "abc",
                "Expected an integer, got: 'abc'",
            ),
        ],
    )
    def test_raises_for_invalid_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
        command: str,
        argument: str,
        message: str,
    ) -> None:
        """Invalid values should fail validation instead of silently persisting."""
        store = _make_store(monkeypatch, tmp_path)

        with pytest.raises(ValueError, match=message):
            handle_programmatic_setting_command(command, argument, agent_store=store)

    def test_updates_nested_fields_and_preserves_other_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        """Updating one nested setting should not clobber sibling values."""
        store = _make_store(monkeypatch, tmp_path)
        settings = CliProgrammaticSettings()
        settings = settings.model_copy(
            update={
                "llm": settings.llm.model_copy(
                    update={
                        "model": "openai/gpt-4o-mini",
                        "api_key": SecretStr("test-api-key"),
                        "base_url": "https://example.com/v1",
                    }
                )
            }
        )
        settings.save(store)

        handle_programmatic_setting_command(
            "llm-model",
            "openai/gpt-4.1-mini",
            agent_store=store,
        )
        handle_programmatic_setting_command(
            "default-cells-expanded",
            "on",
            agent_store=store,
        )
        handle_programmatic_setting_command(
            "issue-threshold",
            "0.7",
            agent_store=store,
        )

        reloaded = CliProgrammaticSettings.load(store)

        assert reloaded.llm.model == "openai/gpt-4.1-mini"
        assert reloaded.llm.api_key is not None
        api_key = cast(SecretStr, reloaded.llm.api_key)
        assert api_key.get_secret_value() == "test-api-key"
        assert reloaded.llm.base_url == "https://example.com/v1"
        assert reloaded.cli.default_cells_expanded is True
        assert reloaded.verification.issue_threshold == pytest.approx(0.7)
