"""Tests for AppConfigurationsTab component (minimal, high-impact)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Switch

from openhands_cli.refactor.modals.settings.app_config import AppConfiguration
from openhands_cli.refactor.modals.settings.components.app_configurations_tab import (
    AppConfigurationsTab,
)


class _TestApp(App):
    """Small Textual app to mount the tab under test."""

    def __init__(self, cfg: AppConfiguration):
        super().__init__()
        self.cfg = cfg

    def compose(self) -> ComposeResult:
        with patch.object(AppConfiguration, "load", return_value=self.cfg) as _:
            yield AppConfigurationsTab()


class TestAppConfigurationsTab:
    @pytest.mark.parametrize("display_cost_per_action", [True, False])
    def test_init_calls_load_and_stores_config(self, display_cost_per_action: bool):
        cfg = AppConfiguration(display_cost_per_action=display_cost_per_action)

        with patch.object(AppConfiguration, "load", return_value=cfg) as mock_load:
            tab = AppConfigurationsTab()

        mock_load.assert_called_once()
        assert tab.app_config == cfg

    @pytest.mark.asyncio
    @pytest.mark.parametrize("initial_value", [True, False])
    async def test_compose_renders_switch_with_loaded_value(self, initial_value: bool):
        cfg = AppConfiguration(display_cost_per_action=initial_value)
        app = _TestApp(cfg)

        async with app.run_test():
            tab = app.query_one(AppConfigurationsTab)
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
    async def test_get_app_config_reflects_current_switch_value(
        self, initial_value: bool, new_value: bool
    ):
        cfg = AppConfiguration(display_cost_per_action=initial_value)
        app = _TestApp(cfg)

        async with app.run_test():
            tab = app.query_one(AppConfigurationsTab)
            switch = tab.query_one("#display_cost_switch", Switch)

            # simulate user change
            switch.value = new_value

            result = tab.get_app_config()
            assert isinstance(result, AppConfiguration)
            assert result.display_cost_per_action is new_value

    @pytest.mark.asyncio
    async def test_switch_click_toggles_state(self):
        cfg = AppConfiguration(display_cost_per_action=False)
        app = _TestApp(cfg)

        async with app.run_test() as pilot:
            tab = app.query_one(AppConfigurationsTab)
            switch = tab.query_one("#display_cost_switch", Switch)

            assert switch.value is False
            await pilot.click(switch)
            assert switch.value is True
