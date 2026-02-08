"""E2E snapshot test for creating an agent plan conversation.

This test validates the complete conversation flow:
1. User types "create a dummy plan"
2. Agent processes via mock LLM
3. Task tracker creates a plan
4. Result is displayed showing the task list
"""

import pytest
from textual.pilot import Pilot

from .helpers import type_text, wait_for_app_ready, wait_for_idle


class TestCreatingAgentPlan:
    """Test creating an agent plan conversation."""

    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["creating_agent_plan"], indirect=True
    )
    def test_creating_agent_plan_conversation(
        self, snap_compare, mock_llm_with_trajectory
    ):
        """Test complete conversation: type 'create a dummy plan', submit, see result.

        This test:
        1. Starts the real OpenHandsApp
        2. Types "create a dummy plan" in the input
        3. Presses Enter to submit
        4. Waits for the agent to process via mock LLM
        5. Captures snapshot showing the task list output
        """
        # Lazy import AFTER fixture has patched locations
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp

        async def run_conversation(pilot: Pilot):
            """Simulate user typing and submitting a command."""
            # Wait for app to fully initialize
            await wait_for_app_ready(pilot)

            # Type the command
            await type_text(pilot, "create a dummy plan")

            # Press Enter to submit
            await pilot.press("enter")

            # Wait for all animations to complete (indicates processing finished)
            await wait_for_idle(pilot)

        # Use fixed conversation ID from fixture for deterministic snapshots
        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=NeverConfirm(),
            resume_conversation_id=mock_llm_with_trajectory["conversation_id"],
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=run_conversation,
        )
