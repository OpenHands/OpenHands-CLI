"""E2E snapshot test for echo hello world conversation.

This test validates the complete conversation flow:
1. User types "echo hello world"
2. Agent processes via mock LLM
3. Terminal command executes
4. Result is displayed
"""

from textual.pilot import Pilot


class TestEchoHelloWorld:
    """Test echo hello world conversation."""

    def test_echo_hello_world_conversation(self, snap_compare, mock_llm_setup):
        """Test complete conversation: type 'echo hello world', submit, see result.

        This test:
        1. Starts the real OpenHandsApp
        2. Types "echo hello world" in the input
        3. Presses Enter to submit
        4. Waits for the agent to process via mock LLM
        5. Captures snapshot showing the terminal output
        """
        # Lazy import AFTER fixture has patched locations
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp
        from openhands_cli.tui.widgets import InputField

        async def run_conversation(pilot: Pilot):
            """Simulate user typing and submitting a command."""
            app = pilot.app

            # Wait for app to fully initialize
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

            # Find and focus the input field
            try:
                input_field = app.query_one(InputField)
                input_field.focus_input()
                await pilot.pause()
            except Exception:
                # App might not be fully initialized
                await pilot.pause()
                await pilot.pause()
                input_field = app.query_one(InputField)
                input_field.focus_input()
                await pilot.pause()

            # Type the command
            for char in "echo hello world":
                await pilot.press(char)
            await pilot.pause()

            # Press Enter to submit
            await pilot.press("enter")

            # Wait for agent to process (give it time to call mock LLM and execute)
            for _ in range(50):
                await pilot.pause()
                # Check if conversation is still running
                runner = getattr(app, "conversation_runner", None)
                if runner is not None and not runner.is_running:
                    break

            # Final pause to let UI update
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

        # Locations are already patched by the fixture via monkeypatch
        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=NeverConfirm(),
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=run_conversation,
        )
