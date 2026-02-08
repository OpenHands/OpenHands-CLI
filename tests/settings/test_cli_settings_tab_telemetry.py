"""Tests for the CLI settings tab component."""

from unittest.mock import patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Switch

from openhands_cli.stores import CliSettings
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.modals.settings.components.cli_settings_tab import CliSettingsTab


class CliSettingsTestApp(App):
    """Minimal Textual App that mounts a CliSettingsTab."""

    def __init__(self, cli_settings: CliSettings) -> None:
        super().__init__()
        self.cli_settings = cli_settings
        self.register_theme(OPENHANDS_THEME)
        self.theme = "openhands"

    def compose(self) -> ComposeResult:
        with patch.object(CliSettings, "load", return_value=self.cli_settings):
            yield CliSettingsTab()


@pytest.mark.asyncio
async def test_telemetry_switch_present() -> None:
    """Test that the telemetry switch is present in the settings tab."""
    cli_settings = CliSettings(
        enable_telemetry=True,
        enable_critic=False,
    )

    app = CliSettingsTestApp(cli_settings)

    async with app.run_test() as pilot:
        await pilot.pause()

        # Check that telemetry switch is present
        telemetry_switch = app.query_one("#enable_telemetry_switch", Switch)
        assert telemetry_switch is not None
        assert telemetry_switch.value is True


@pytest.mark.asyncio
async def test_telemetry_switch_disabled_when_critic_enabled() -> None:
    """Test that telemetry switch is disabled when critic is enabled."""
    cli_settings = CliSettings(
        enable_telemetry=False,  # Even if telemetry is disabled
        enable_critic=True,  # Critic forces telemetry on
    )

    app = CliSettingsTestApp(cli_settings)

    async with app.run_test() as pilot:
        await pilot.pause()

        # Check that telemetry switch is disabled and forced on
        telemetry_switch = app.query_one("#enable_telemetry_switch", Switch)
        assert telemetry_switch.disabled is True
        assert telemetry_switch.value is True  # Forced on


@pytest.mark.asyncio
async def test_telemetry_switch_enabled_when_critic_disabled() -> None:
    """Test that telemetry switch is enabled when critic is disabled."""
    cli_settings = CliSettings(
        enable_telemetry=False,
        enable_critic=False,
    )

    app = CliSettingsTestApp(cli_settings)

    async with app.run_test() as pilot:
        await pilot.pause()

        # Check that telemetry switch is enabled
        telemetry_switch = app.query_one("#enable_telemetry_switch", Switch)
        assert telemetry_switch.disabled is False
        assert telemetry_switch.value is False


@pytest.mark.asyncio
async def test_telemetry_switch_updates_when_critic_toggled() -> None:
    """Test that telemetry switch updates when critic is toggled."""
    cli_settings = CliSettings(
        enable_telemetry=False,
        enable_critic=False,
    )

    app = CliSettingsTestApp(cli_settings)

    async with app.run_test() as pilot:
        await pilot.pause()

        # Initially telemetry switch should be enabled
        telemetry_switch = app.query_one("#enable_telemetry_switch", Switch)
        critic_switch = app.query_one("#enable_critic_switch", Switch)

        assert telemetry_switch.disabled is False
        assert telemetry_switch.value is False

        # Enable critic
        critic_switch.value = True
        await pilot.pause()

        # Telemetry should now be forced on and disabled
        assert telemetry_switch.disabled is True
        assert telemetry_switch.value is True

        # Disable critic
        critic_switch.value = False
        await pilot.pause()

        # Telemetry should be enabled again (but still True from before)
        assert telemetry_switch.disabled is False


@pytest.mark.asyncio
async def test_get_cli_settings_includes_telemetry() -> None:
    """Test that get_cli_settings returns telemetry setting."""
    cli_settings = CliSettings(
        enable_telemetry=True,
        enable_critic=False,
    )

    app = CliSettingsTestApp(cli_settings)

    async with app.run_test() as pilot:
        await pilot.pause()

        cli_settings_tab = app.query_one(CliSettingsTab)
        settings = cli_settings_tab.get_cli_settings()

        assert settings.enable_telemetry is True
        assert settings.enable_critic is False
