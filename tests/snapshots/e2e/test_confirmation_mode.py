"""E2E snapshot tests for confirmation mode multi-turn conversation.

These tests validate a multi-turn conversation with confirmation mode,
capturing snapshots at key points including when the confirmation panel
is displayed.

With the non-blocking confirmation architecture:
1. Workers exit when confirmation is needed (no blocking)
2. UI shows confirmation panel via Textual messages
3. Snapshots can be captured while confirmation panel is displayed

Tests capture:
1. Confirmation panel displayed (waiting for user input)
2. After first turn (selecting "Auto LOW/MED" to confirm and set policy)
3. After HIGH risk confirmation with "Yes"
4. Final state after all three turns complete
"""

import pytest
from textual.pilot import Pilot

from .helpers import type_text, wait_for_app_ready, wait_for_idle


class TestConfirmationPanelDisplayed:
    """Test that confirmation panel is properly displayed."""

    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["confirmation_mode"], indirect=True
    )
    def test_confirmation_panel_displayed(
        self, snap_compare, mock_llm_with_trajectory
    ):
        """Snapshot showing confirmation panel while waiting for user input.

        User types "echo hello world" and the confirmation panel is shown.
        Since workers are non-blocking, the snapshot captures the panel.
        """
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp

        async def run_to_confirmation_panel(pilot: Pilot):
            await wait_for_app_ready(pilot)

            # Type first command
            await type_text(pilot, "echo hello world")
            await pilot.press("enter")

            # Wait for worker to process and show confirmation panel
            # With non-blocking workers, wait_for_idle completes after
            # the worker posts ConfirmationNeeded and exits
            await wait_for_idle(pilot)

            # The confirmation panel should now be visible

        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=AlwaysConfirm(),
            resume_conversation_id=mock_llm_with_trajectory["conversation_id"],
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=run_to_confirmation_panel,
        )


class TestConfirmationModePhase1:
    """Phase 1: First turn complete after selecting Auto LOW/MED."""

    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["confirmation_mode"], indirect=True
    )
    def test_phase1_after_auto_low_med_selected(
        self, snap_compare, mock_llm_with_trajectory
    ):
        """Snapshot after first turn completes with policy change.

        User types "echo hello world", selects "Auto LOW/MED" which:
        1. Confirms the pending action
        2. Sets ConfirmRisky policy for future actions
        """
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp

        async def run_phase1(pilot: Pilot):
            await wait_for_app_ready(pilot)

            # Type first command
            await type_text(pilot, "echo hello world")
            await pilot.press("enter")

            # Wait for confirmation panel to appear
            await wait_for_idle(pilot)

            # Select "Auto LOW/MED" (4th option, index 3) to confirm and set policy
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("enter")

            # Wait for action to complete
            await wait_for_idle(pilot)

        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=AlwaysConfirm(),
            resume_conversation_id=mock_llm_with_trajectory["conversation_id"],
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=run_phase1,
        )


class TestConfirmationModePhase2:
    """Phase 2: Second turn complete after confirming HIGH risk action."""

    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["confirmation_mode"], indirect=True
    )
    def test_phase2_after_high_risk_confirmed(
        self, snap_compare, mock_llm_with_trajectory
    ):
        """Snapshot after second turn completes with HIGH risk confirmation.

        User sends "do it again, mark it as a high risk action though",
        confirms with "Yes", and the action completes.
        """
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp

        async def run_phase2(pilot: Pilot):
            await wait_for_app_ready(pilot)

            # Turn 1: First command with policy change
            await type_text(pilot, "echo hello world")
            await pilot.press("enter")
            await wait_for_idle(pilot)

            # Select "Auto LOW/MED"
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("enter")
            await wait_for_idle(pilot)

            # Turn 2: HIGH risk command
            await type_text(pilot, "do it again, mark it as a high risk action though")
            await pilot.press("enter")
            await wait_for_idle(pilot)

            # Confirm with "Yes" (default selection)
            await pilot.press("enter")
            await wait_for_idle(pilot)

        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=AlwaysConfirm(),
            resume_conversation_id=mock_llm_with_trajectory["conversation_id"],
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=run_phase2,
        )


class TestConfirmationModePhase3:
    """Phase 3: Final state after all three turns complete."""

    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["confirmation_mode"], indirect=True
    )
    def test_phase3_final_state(self, snap_compare, mock_llm_with_trajectory):
        """Snapshot of final state after all three turns complete.

        User sends "once more, don't mark it as high risk this time"
        which is LOW risk and auto-approved under ConfirmRisky policy.
        """
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp

        async def run_phase3(pilot: Pilot):
            await wait_for_app_ready(pilot)

            # Turn 1: First command with policy change
            await type_text(pilot, "echo hello world")
            await pilot.press("enter")
            await wait_for_idle(pilot)

            # Select "Auto LOW/MED"
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("enter")
            await wait_for_idle(pilot)

            # Turn 2: HIGH risk command
            await type_text(pilot, "do it again, mark it as a high risk action though")
            await pilot.press("enter")
            await wait_for_idle(pilot)

            # Confirm with "Yes"
            await pilot.press("enter")
            await wait_for_idle(pilot)

            # Turn 3: LOW risk command (auto-approved with ConfirmRisky)
            await type_text(pilot, "once more, don't mark it as high risk this time")
            await pilot.press("enter")

            # Wait for idle since LOW risk is auto-approved
            await wait_for_idle(pilot)

        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=AlwaysConfirm(),
            resume_conversation_id=mock_llm_with_trajectory["conversation_id"],
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=run_phase3,
        )
