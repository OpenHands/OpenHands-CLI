"""E2E snapshot test for app initial state.

This test captures the welcome screen and initial UI layout
before any user interaction.
"""

from textual.pilot import Pilot

from .helpers import wait_for_app_ready


class TestAppInitialState:
    """Test app initial state."""

    def test_app_initial_state(self, snap_compare, mock_llm_setup):
        """Snapshot of app initial state showing splash screen.

        This captures the welcome screen and initial UI layout.
        """
        # Lazy import AFTER fixture has patched locations
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp

        async def wait_for_init(pilot: Pilot):
            """Wait for app to initialize."""
            await wait_for_app_ready(pilot)

        # Locations are already patched by the fixture via monkeypatch
        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=NeverConfirm(),
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=wait_for_init,
        )
