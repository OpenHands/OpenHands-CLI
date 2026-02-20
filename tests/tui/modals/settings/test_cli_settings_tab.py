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
    @pytest.mark.parametrize("default_cells_expanded", [True, False])
    def test_init_calls_load_and_stores_config(self, default_cells_expanded: bool):
        cfg = CliSettings(default_cells_expanded=default_cells_expanded)

        with patch.object(CliSettings, "load", return_value=cfg) as mock_load:
            tab = CliSettingsTab()

        mock_load.assert_called_once()
        assert tab.cli_settings == cfg

    @pytest.mark.asyncio
    @pytest.mark.parametrize("initial_value", [True, False])
    async def test_compose_renders_default_cells_expanded_switch(
        self, initial_value: bool
    ):
        cfg = CliSettings(default_cells_expanded=initial_value)
        app = _TestApp(cfg)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#default_cells_expanded_switch", Switch)
            assert switch.value is initial_value

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "initial_value, new_value",
        [
            (False, True),
            (True, False),
        ],
    )
    async def test_get_cli_settings_reflects_default_cells_expanded(
        self, initial_value: bool, new_value: bool
    ):
        cfg = CliSettings(default_cells_expanded=initial_value)
        app = _TestApp(cfg)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#default_cells_expanded_switch", Switch)

            # simulate user change
            switch.value = new_value

            result = tab.get_cli_settings()
            assert isinstance(result, CliSettings)
            assert result.default_cells_expanded is new_value

    @pytest.mark.asyncio
    @pytest.mark.parametrize("initial_value", [True, False])
    async def test_compose_renders_auto_open_plan_panel_switch(
        self, initial_value: bool
    ):
        """Verify the auto_open_plan_panel switch is rendered with correct value."""
        cfg = CliSettings(auto_open_plan_panel=initial_value)
        app = _TestApp(cfg)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#auto_open_plan_panel_switch", Switch)
            assert switch.value is initial_value

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "initial_value, new_value",
        [
            (False, True),
            (True, False),
        ],
    )
    async def test_get_cli_settings_reflects_auto_open_plan_panel(
        self, initial_value: bool, new_value: bool
    ):
        """Verify get_cli_settings() captures auto_open_plan_panel switch state."""
        cfg = CliSettings(auto_open_plan_panel=initial_value)
        app = _TestApp(cfg)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#auto_open_plan_panel_switch", Switch)

            # simulate user change
            switch.value = new_value

            result = tab.get_cli_settings()
            assert isinstance(result, CliSettings)
            assert result.auto_open_plan_panel is new_value
