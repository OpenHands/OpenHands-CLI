"""Snapshot tests for CriticSettingsTab component.

These tests capture the visual appearance of the critic settings tab
in various states for visual regression testing.

To update snapshots when intentional changes are made:
    pytest tests/snapshots/test_critic_settings_tab_snapshots.py --snapshot-update

To run these tests:
    pytest tests/snapshots/test_critic_settings_tab_snapshots.py
"""

import importlib.resources as resources

from textual.app import App, ComposeResult
from textual.widgets import Footer, Input, Switch

from openhands_cli.stores.cli_settings import (
    DEFAULT_CRITIC_THRESHOLD,
    DEFAULT_ISSUE_THRESHOLD,
    CriticSettings,
)
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.modals.settings.components.critic_settings_tab import (
    CriticSettingsTab,
)


class TestCriticSettingsTabSnapshots:
    """Snapshot tests for the CriticSettingsTab component."""

    def test_critic_settings_tab_default_state(self, snap_compare):
        """Snapshot test for critic settings tab with default values."""

        class CriticSettingsTabTestApp(App):
            CSS_PATH = str(
                resources.files("openhands_cli.tui.modals.settings")
                / "settings_screen.tcss"
            )

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_theme(OPENHANDS_THEME)
                self.theme = OPENHANDS_THEME.name

            def compose(self) -> ComposeResult:
                yield CriticSettingsTab(
                    initial_settings=CriticSettings(
                        enable_critic=True,
                        enable_iterative_refinement=False,
                        critic_threshold=DEFAULT_CRITIC_THRESHOLD,
                        issue_threshold=DEFAULT_ISSUE_THRESHOLD,
                    )
                )
                yield Footer()

        assert snap_compare(
            CriticSettingsTabTestApp(),
            terminal_size=(80, 35),
        )

    def test_critic_settings_tab_refinement_enabled(self, snap_compare):
        """Snapshot test for critic settings tab with refinement enabled."""

        class CriticSettingsTabEnabledApp(App):
            CSS_PATH = str(
                resources.files("openhands_cli.tui.modals.settings")
                / "settings_screen.tcss"
            )

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_theme(OPENHANDS_THEME)
                self.theme = OPENHANDS_THEME.name

            def compose(self) -> ComposeResult:
                yield CriticSettingsTab(
                    initial_settings=CriticSettings(
                        enable_critic=True,
                        enable_iterative_refinement=True,
                        critic_threshold=0.7,
                        issue_threshold=0.8,
                    )
                )
                yield Footer()

        assert snap_compare(
            CriticSettingsTabEnabledApp(),
            terminal_size=(80, 35),
        )

    def test_critic_settings_tab_all_disabled(self, snap_compare):
        """Snapshot test for critic settings tab with everything disabled."""

        class CriticSettingsTabDisabledApp(App):
            CSS_PATH = str(
                resources.files("openhands_cli.tui.modals.settings")
                / "settings_screen.tcss"
            )

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_theme(OPENHANDS_THEME)
                self.theme = OPENHANDS_THEME.name

            def compose(self) -> ComposeResult:
                yield CriticSettingsTab(
                    initial_settings=CriticSettings(
                        enable_critic=False,
                        enable_iterative_refinement=False,
                        critic_threshold=DEFAULT_CRITIC_THRESHOLD,
                        issue_threshold=DEFAULT_ISSUE_THRESHOLD,
                    )
                )
                yield Footer()

        assert snap_compare(
            CriticSettingsTabDisabledApp(),
            terminal_size=(80, 35),
        )

    def test_critic_settings_tab_toggle_refinement(self, snap_compare):
        """Snapshot test for enabling iterative refinement via switch."""

        class CriticSettingsTabToggleApp(App):
            CSS_PATH = str(
                resources.files("openhands_cli.tui.modals.settings")
                / "settings_screen.tcss"
            )

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_theme(OPENHANDS_THEME)
                self.theme = OPENHANDS_THEME.name

            def compose(self) -> ComposeResult:
                yield CriticSettingsTab(
                    initial_settings=CriticSettings(
                        enable_critic=True,
                        enable_iterative_refinement=False,
                        critic_threshold=DEFAULT_CRITIC_THRESHOLD,
                        issue_threshold=DEFAULT_ISSUE_THRESHOLD,
                    )
                )
                yield Footer()

        async def enable_refinement(pilot):
            # Find and toggle the refinement switch
            switch = pilot.app.query_one("#enable_iterative_refinement_switch", Switch)
            switch.value = True
            await pilot.pause()

        assert snap_compare(
            CriticSettingsTabToggleApp(),
            terminal_size=(80, 35),
            run_before=enable_refinement,
        )

    def test_critic_settings_tab_invalid_threshold(self, snap_compare):
        """Snapshot test for invalid threshold input showing validation error."""

        class CriticSettingsTabInvalidApp(App):
            CSS_PATH = str(
                resources.files("openhands_cli.tui.modals.settings")
                / "settings_screen.tcss"
            )

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_theme(OPENHANDS_THEME)
                self.theme = OPENHANDS_THEME.name

            def compose(self) -> ComposeResult:
                yield CriticSettingsTab(
                    initial_settings=CriticSettings(
                        enable_critic=True,
                        enable_iterative_refinement=True,
                        critic_threshold=DEFAULT_CRITIC_THRESHOLD,
                        issue_threshold=DEFAULT_ISSUE_THRESHOLD,
                    )
                )
                yield Footer()

        async def set_invalid_value(pilot):
            # Find the threshold input and set an invalid value
            threshold_input = pilot.app.query_one("#critic_threshold_input", Input)
            threshold_input.value = "150"  # Invalid: > 100
            await pilot.pause()

        assert snap_compare(
            CriticSettingsTabInvalidApp(),
            terminal_size=(80, 35),
            run_before=set_invalid_value,
        )
