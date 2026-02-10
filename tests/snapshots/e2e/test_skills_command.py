"""E2E snapshot test for /skills command.

This test validates the /skills command flow:
1. User types "/skills"
2. The loaded resources (skills, hooks, MCPs) are displayed
"""

from textual.pilot import Pilot

from .helpers import type_text, wait_for_app_ready, wait_for_idle


class TestSkillsCommand:
    """Test /skills command."""

    def test_skills_command(self, snap_compare, mock_llm_setup):
        """Test /skills command displays loaded resources.

        This test:
        1. Starts the real OpenHandsApp
        2. Types "/skills" in the input
        3. Presses Enter to select from dropdown
        4. Presses Enter again to execute the command
        5. Captures snapshot showing the loaded resources
        """
        # Lazy import AFTER fixture has patched locations
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp

        async def run_skills_command(pilot: Pilot):
            """Simulate user typing and executing /skills command."""
            # Wait for app to fully initialize
            await wait_for_app_ready(pilot)

            # Type the command
            await type_text(pilot, "/skills")

            # First enter selects from dropdown, second enter executes /skills
            await pilot.press("enter")
            await pilot.press("enter")

            # Wait for all animations to complete
            await wait_for_idle(pilot)

        # Use fixed conversation ID from fixture for deterministic snapshots
        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=NeverConfirm(),
            resume_conversation_id=mock_llm_setup["conversation_id"],
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=run_skills_command,
        )
