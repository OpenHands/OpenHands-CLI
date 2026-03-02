"""Tests for CriticSettingsTab component."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Checkbox, Input

from openhands_cli.stores.cli_settings import (
    DEFAULT_CRITIC_THRESHOLD,
    DEFAULT_ISSUE_THRESHOLD,
    CriticSettings,
)
from openhands_cli.tui.modals.settings.components.critic_settings_tab import (
    CriticSettingsTab,
    ThresholdInput,
)


class _TestApp(App):
    """Small Textual app to mount the tab under test."""

    def __init__(self, initial_settings: CriticSettings | None = None):
        super().__init__()
        self.initial_settings = initial_settings

    def compose(self) -> ComposeResult:
        yield CriticSettingsTab(initial_settings=self.initial_settings)


class TestCriticSettingsTab:
    def test_init_accepts_initial_settings(self):
        """Verify tab accepts initial_settings CriticSettings object."""
        initial = CriticSettings(
            enable_critic=True,
            enable_iterative_refinement=True,
            critic_threshold=0.7,
            issue_threshold=0.8,
        )
        tab = CriticSettingsTab(initial_settings=initial)
        assert tab._initial_settings == initial

    def test_init_defaults_to_critic_settings(self):
        """Verify tab defaults to CriticSettings when no initial_settings provided."""
        tab = CriticSettingsTab()
        assert isinstance(tab._initial_settings, CriticSettings)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("initial_value", [True, False])
    async def test_compose_renders_enable_critic_switch(self, initial_value: bool):
        """Verify the enable_critic switch is rendered with correct value."""
        initial = CriticSettings(enable_critic=initial_value)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CriticSettingsTab)
            switch = tab.query_one("#enable_critic_switch", Checkbox)
            assert switch.value is initial_value

    @pytest.mark.asyncio
    @pytest.mark.parametrize("initial_value", [True, False])
    async def test_compose_renders_enable_refinement_switch(self, initial_value: bool):
        """Verify the enable_iterative_refinement switch is rendered correctly."""
        initial = CriticSettings(enable_iterative_refinement=initial_value)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CriticSettingsTab)
            switch = tab.query_one("#enable_iterative_refinement_switch", Checkbox)
            assert switch.value is initial_value

    @pytest.mark.asyncio
    async def test_threshold_inputs_disabled_when_refinement_off(self):
        """Verify threshold inputs are disabled when refinement is off."""
        initial = CriticSettings(enable_iterative_refinement=False)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CriticSettingsTab)
            critic_input = tab.query_one("#critic_threshold_input", Input)
            issue_input = tab.query_one("#issue_threshold_input", Input)
            assert critic_input.disabled is True
            assert issue_input.disabled is True

    @pytest.mark.asyncio
    async def test_threshold_inputs_enabled_when_refinement_on(self):
        """Verify threshold inputs are enabled when refinement is on."""
        initial = CriticSettings(enable_iterative_refinement=True)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CriticSettingsTab)
            critic_input = tab.query_one("#critic_threshold_input", Input)
            issue_input = tab.query_one("#issue_threshold_input", Input)
            assert critic_input.disabled is False
            assert issue_input.disabled is False

    @pytest.mark.asyncio
    async def test_toggle_refinement_enables_threshold_inputs(self):
        """Verify toggling refinement on enables the threshold inputs."""
        initial = CriticSettings(enable_iterative_refinement=False)
        app = _TestApp(initial_settings=initial)

        async with app.run_test() as pilot:
            tab = app.query_one(CriticSettingsTab)
            refinement_switch = tab.query_one(
                "#enable_iterative_refinement_switch", Checkbox
            )
            critic_input = tab.query_one("#critic_threshold_input", Input)
            issue_input = tab.query_one("#issue_threshold_input", Input)

            # Initially disabled
            assert critic_input.disabled is True
            assert issue_input.disabled is True

            # Enable refinement by toggling the switch (this triggers the event)
            refinement_switch.toggle()
            await pilot.pause()

            # Now should be enabled
            assert critic_input.disabled is False
            assert issue_input.disabled is False

    @pytest.mark.asyncio
    async def test_toggle_refinement_disables_threshold_inputs(self):
        """Verify toggling refinement off disables the threshold inputs."""
        initial = CriticSettings(enable_iterative_refinement=True)
        app = _TestApp(initial_settings=initial)

        async with app.run_test() as pilot:
            tab = app.query_one(CriticSettingsTab)
            refinement_switch = tab.query_one(
                "#enable_iterative_refinement_switch", Checkbox
            )
            critic_input = tab.query_one("#critic_threshold_input", Input)
            issue_input = tab.query_one("#issue_threshold_input", Input)

            # Initially enabled
            assert critic_input.disabled is False
            assert issue_input.disabled is False

            # Disable refinement by toggling the switch (this triggers the event)
            refinement_switch.toggle()
            await pilot.pause()

            # Now should be disabled
            assert critic_input.disabled is True
            assert issue_input.disabled is True

    @pytest.mark.asyncio
    async def test_get_updated_fields_returns_all_fields(self):
        """Verify get_updated_fields() returns all critic settings fields."""
        initial = CriticSettings(
            enable_critic=True,
            enable_iterative_refinement=True,
            critic_threshold=0.6,
            issue_threshold=0.75,
        )
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CriticSettingsTab)
            result = tab.get_updated_fields()

            assert set(result.keys()) == {
                "enable_critic",
                "enable_iterative_refinement",
                "critic_threshold",
                "issue_threshold",
            }

    @pytest.mark.asyncio
    async def test_get_updated_fields_reflects_switch_changes(self):
        """Verify get_updated_fields() captures switch changes."""
        initial = CriticSettings(enable_critic=False, enable_iterative_refinement=False)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CriticSettingsTab)
            critic_switch = tab.query_one("#enable_critic_switch", Checkbox)
            refinement_switch = tab.query_one(
                "#enable_iterative_refinement_switch", Checkbox
            )

            # Change switch values
            critic_switch.value = True
            refinement_switch.value = True

            result = tab.get_updated_fields()
            assert result["enable_critic"] is True
            assert result["enable_iterative_refinement"] is True

    @pytest.mark.asyncio
    async def test_get_updated_fields_parses_valid_threshold(self):
        """Verify get_updated_fields() correctly parses valid threshold values."""
        initial = CriticSettings(enable_iterative_refinement=True)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CriticSettingsTab)
            critic_input = tab.query_one("#critic_threshold_input", Input)
            issue_input = tab.query_one("#issue_threshold_input", Input)

            # Set valid values
            critic_input.value = "70"
            issue_input.value = "85"

            result = tab.get_updated_fields()
            assert result["critic_threshold"] == 0.7
            assert result["issue_threshold"] == 0.85

    @pytest.mark.asyncio
    async def test_get_updated_fields_uses_default_for_invalid_threshold(self):
        """Verify get_updated_fields() uses default for invalid threshold values."""
        initial = CriticSettings(enable_iterative_refinement=True)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CriticSettingsTab)
            critic_input = tab.query_one("#critic_threshold_input", Input)
            issue_input = tab.query_one("#issue_threshold_input", Input)

            # Set invalid values
            critic_input.value = "abc"
            issue_input.value = "150"  # Out of range

            result = tab.get_updated_fields()
            assert result["critic_threshold"] == DEFAULT_CRITIC_THRESHOLD
            assert result["issue_threshold"] == DEFAULT_ISSUE_THRESHOLD

    @pytest.mark.asyncio
    async def test_get_updated_fields_uses_default_for_out_of_range_threshold(self):
        """Verify get_updated_fields() uses default for out-of-range values."""
        initial = CriticSettings(enable_iterative_refinement=True)
        app = _TestApp(initial_settings=initial)

        async with app.run_test():
            tab = app.query_one(CriticSettingsTab)
            critic_input = tab.query_one("#critic_threshold_input", Input)
            issue_input = tab.query_one("#issue_threshold_input", Input)

            # Set out of range values
            critic_input.value = "0"  # Below 1
            issue_input.value = "101"  # Above 100

            result = tab.get_updated_fields()
            assert result["critic_threshold"] == DEFAULT_CRITIC_THRESHOLD
            assert result["issue_threshold"] == DEFAULT_ISSUE_THRESHOLD


class TestThresholdInput:
    @pytest.mark.asyncio
    async def test_validate_input_valid_value(self):
        """Verify validate_input returns True for valid values."""

        class ThresholdInputTestApp(App):
            def compose(self) -> ComposeResult:
                yield ThresholdInput(
                    label="Test",
                    description="Test description",
                    input_id="test_input",
                    value=0.6,
                )

        app = ThresholdInputTestApp()

        async with app.run_test():
            threshold_input = app.query_one(ThresholdInput)
            assert threshold_input.validate_input("50") is True
            assert "invalid" not in threshold_input.classes

    @pytest.mark.asyncio
    async def test_validate_input_invalid_value(self):
        """Verify validate_input returns False and adds class for invalid values."""

        class ThresholdInputTestApp(App):
            def compose(self) -> ComposeResult:
                yield ThresholdInput(
                    label="Test",
                    description="Test description",
                    input_id="test_input",
                    value=0.6,
                )

        app = ThresholdInputTestApp()

        async with app.run_test():
            threshold_input = app.query_one(ThresholdInput)
            assert threshold_input.validate_input("150") is False
            assert "invalid" in threshold_input.classes

    @pytest.mark.asyncio
    async def test_validate_input_non_numeric(self):
        """Verify validate_input returns False for non-numeric values."""

        class ThresholdInputTestApp(App):
            def compose(self) -> ComposeResult:
                yield ThresholdInput(
                    label="Test",
                    description="Test description",
                    input_id="test_input",
                    value=0.6,
                )

        app = ThresholdInputTestApp()

        async with app.run_test():
            threshold_input = app.query_one(ThresholdInput)
            assert threshold_input.validate_input("abc") is False
            assert "invalid" in threshold_input.classes

    @pytest.mark.asyncio
    async def test_validate_input_boundary_values(self):
        """Verify validate_input handles boundary values correctly."""

        class ThresholdInputTestApp(App):
            def compose(self) -> ComposeResult:
                yield ThresholdInput(
                    label="Test",
                    description="Test description",
                    input_id="test_input",
                    value=0.6,
                )

        app = ThresholdInputTestApp()

        async with app.run_test():
            threshold_input = app.query_one(ThresholdInput)

            # Valid boundaries
            assert threshold_input.validate_input("1") is True
            assert threshold_input.validate_input("100") is True

            # Invalid boundaries
            assert threshold_input.validate_input("0") is False
            assert threshold_input.validate_input("101") is False
