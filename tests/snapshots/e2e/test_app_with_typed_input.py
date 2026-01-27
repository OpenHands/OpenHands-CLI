"""E2E snapshot test for app with typed input.

This test captures the UI state while the user is typing
their command, before submitting.
"""

from textual.pilot import Pilot

from .helpers import type_text, wait_for_app_ready, wait_for_idle, wait_for_widget


class TestAppWithTypedInput:
    """Test app state with typed input."""

    def test_app_with_typed_input(self, snap_compare, mock_llm_setup):
        """Snapshot of app with text typed but not yet submitted.

        This captures the UI state while the user is typing their command.
        """
        # Lazy import AFTER fixture has patched locations
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp
        from openhands_cli.tui.widgets import InputField

        async def type_command(pilot: Pilot):
            """Type command without submitting."""
            # Wait for app to fully initialize
            await wait_for_app_ready(pilot)

            # Find and focus the input field
            input_field = await wait_for_widget(pilot, InputField)
            input_field.focus_input()
            await wait_for_idle(pilot)

            # Type the command
            await type_text(pilot, "echo hello world")

        # Locations are already patched by the fixture via monkeypatch
        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=NeverConfirm(),
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=type_command,
        )
