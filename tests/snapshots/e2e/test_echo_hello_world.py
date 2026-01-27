"""E2E snapshot test for echo hello world conversation.

This test validates the complete conversation flow:
1. User types "echo hello world"
2. Agent processes via mock LLM
3. Terminal command executes
4. Result is displayed
"""

from textual.pilot import Pilot

from .helpers import type_text, wait_for_app_ready, wait_for_idle


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

        async def run_conversation(pilot: Pilot):
            """Simulate user typing and submitting a command."""
            # Wait for app to fully initialize
            await wait_for_app_ready(pilot)

            # Type the command
            await type_text(pilot, "echo hello world")

            # Press Enter to submit
            await pilot.press("enter")

            # Wait for all animations to complete (indicates processing finished)
            await wait_for_idle(pilot)

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
