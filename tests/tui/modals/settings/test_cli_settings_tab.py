"""Tests for CliSettingsTab component (minimal, high-impact)."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Checkbox

from openhands_cli.stores.cli_settings import CliSettings
from openhands_cli.tui.modals.settings.components.cli_settings_tab import (
    CliSettingsTab,
)


class _TestApp(App):
    """Small Textual app to mount the tab under test."""

    def __init__(self, initial_settings: CliSettings | None = None):
        super().__init__()
        self.initial_settings = initial_settings

    def compose(self) -> ComposeResult:
        yield CliSettingsTab(initial_settings=self.initial_settings)


class TestCliSettingsTab:
    def test_init_accepts_initial_settings(self):
        """Verify tab accepts initial_settings CliSettings object."""
        initial = CliSettings(default_cells_expanded=True, auto_open_plan_panel=False)
        tab = CliSettingsTab(initial_settings=initial)
        assert tab._initial_settings == initial

    def test_init_defaults_to_cli_settings(self):
        """Verify tab defaults to CliSettings when no initial_settings provided."""
        tab = CliSettingsTab()
        assert isinstance(tab._initial_settings, CliSettings)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("initial_value", [True, False])
    async def test_compose_renders_default_cells_expanded_switch(
        self, initial_value: bool
    ):
        initial = CliSettings(default_cells_expanded=initial_value)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#default_cells_expanded_switch", Checkbox)
            assert switch.value is initial_value

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "initial_value, new_value",
        [
            (False, True),
            (True, False),
        ],
    )
    async def test_get_updated_fields_reflects_default_cells_expanded(
        self, initial_value: bool, new_value: bool
    ):
        initial = CliSettings(default_cells_expanded=initial_value)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#default_cells_expanded_switch", Checkbox)

            # simulate user change
            switch.value = new_value

            result = tab.get_updated_fields()
            assert isinstance(result, dict)
            assert result["default_cells_expanded"] is new_value

    @pytest.mark.asyncio
    @pytest.mark.parametrize("initial_value", [True, False])
    async def test_compose_renders_auto_open_plan_panel_switch(
        self, initial_value: bool
    ):
        """Verify the auto_open_plan_panel switch is rendered with correct value."""
        initial = CliSettings(auto_open_plan_panel=initial_value)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#auto_open_plan_panel_switch", Checkbox)
            assert switch.value is initial_value

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "initial_value, new_value",
        [
            (False, True),
            (True, False),
        ],
    )
    async def test_get_updated_fields_reflects_auto_open_plan_panel(
        self, initial_value: bool, new_value: bool
    ):
        """Verify get_updated_fields() captures auto_open_plan_panel switch state."""
        initial = CliSettings(auto_open_plan_panel=initial_value)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            switch = tab.query_one("#auto_open_plan_panel_switch", Checkbox)

            # simulate user change
            switch.value = new_value

            result = tab.get_updated_fields()
            assert isinstance(result, dict)
            assert result["auto_open_plan_panel"] is new_value

    @pytest.mark.asyncio
    async def test_get_updated_fields_returns_only_managed_fields(self):
        """Verify get_updated_fields() returns only the fields this tab manages."""
        initial = CliSettings(default_cells_expanded=True, auto_open_plan_panel=False)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CliSettingsTab)
            result = tab.get_updated_fields()

            # Should only contain the 2 fields this tab manages
            assert set(result.keys()) == {
                "default_cells_expanded",
                "auto_open_plan_panel",
            }
