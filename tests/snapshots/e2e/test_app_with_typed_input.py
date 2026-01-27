"""E2E snapshot test for app with typed input.

This test captures the UI state while the user is typing
their command, before submitting.
"""

from textual.pilot import Pilot


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
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

            try:
                input_field = pilot.app.query_one(InputField)
                input_field.focus_input()
                await pilot.pause()
            except Exception:
                await pilot.pause()
                input_field = pilot.app.query_one(InputField)
                input_field.focus_input()
                await pilot.pause()

            # Type the command
            for char in "echo hello world":
                await pilot.press(char)
            await pilot.pause()

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
