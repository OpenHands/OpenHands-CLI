"""Tests for CliSettingsTab component (minimal, high-impact)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Switch

from openhands_cli.stores import CliSettings
from openhands_cli.tui.modals.settings.components.cli_settings_tab import (
    CliSettingsTab,
)


class _TestApp(App):
    """Small Textual app to mount the tab under test."""

    def __init__(self, cfg: CliSettings):
        super().__init__()
        self.cfg = cfg

    def compose(self) -> ComposeResult:
        with patch.object(CliSettings, "load", return_value=self.cfg) as _:
            yield CliSettingsTab()


class TestCliSettingsTab:
    @pytest.mark.parametrize("display_cost_per_action", [True, False])
    def test_init_calls_load_and_stores_config(self, display_cost_per_action: bool):
        cfg = CliSettings(display_cost_per_action=display_cost_per_action)

        with patch.object(CliSettings, "load", return_value=cfg) as mock_load:
            tab = CliSettingsTab()

        mock_load.assert_called_once()
        assert tab.cli_settings == cfg

    @pytest.mark.asyncio
    @pytest.mark.parametrize("initial_value", [True, False])
    async def test_compose_renders_switch_with_loaded_value(self, initial_value: bool):
        cfg = CliSettings(display_cost_per_action=initial_value)
        app = _TestApp(cfg)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#display_cost_switch", Switch)
            assert switch.value is initial_value

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "initial_value, new_value",
        [
            (False, True),
            (True, False),
        ],
    )
    async def test_get_cli_settings_reflects_current_switch_value(
        self, initial_value: bool, new_value: bool
    ):
        cfg = CliSettings(display_cost_per_action=initial_value)
        app = _TestApp(cfg)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#display_cost_switch", Switch)

            # simulate user change
            switch.value = new_value

            result = tab.get_cli_settings()
            assert isinstance(result, CliSettings)
            assert result.display_cost_per_action is new_value

    @pytest.mark.asyncio
    async def test_switch_click_toggles_state(self):
        cfg = CliSettings(display_cost_per_action=False)
        app = _TestApp(cfg)

        async with app.run_test() as pilot:
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#display_cost_switch", Switch)

            assert switch.value is False
            await pilot.click(switch)
            assert switch.value is True
