"""E2E snapshot tests for confirmation mode multi-turn conversation.

These tests validate a multi-turn conversation with confirmation mode,
capturing snapshots at key points after confirmations are resolved.

Note: Due to Textual's snapshot mechanism requiring the app to be "idle",
we cannot capture snapshots while a confirmation panel is being displayed
(as a worker is blocked waiting for user input). Instead, we capture
snapshots after each confirmation is resolved:

1. After first turn (selecting "Auto LOW/MED" to confirm and set policy)
2. After second turn (HIGH risk action confirmed with "Yes")
3. After third turn (LOW risk auto-approved, final state)
"""

import asyncio

import pytest
from textual.pilot import Pilot

from .helpers import type_text, wait_for_app_ready, wait_for_idle


async def wait_for_confirmation_panel(pilot: Pilot, timeout: float = 5.0) -> None:
    """Wait for confirmation panel to render.

    When waiting for a confirmation panel, we can't use wait_for_idle because
    a worker is blocked waiting for user input. Instead, we wait for animations
    and add a small delay to ensure the UI is fully rendered.
    """
    # Give time for the worker to start and the confirmation panel to be mounted
    await asyncio.sleep(1.0)
    await pilot.wait_for_scheduled_animations()
    await asyncio.sleep(0.5)
    await pilot.wait_for_scheduled_animations()


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

            # Wait for confirmation panel to render
            await wait_for_confirmation_panel(pilot)

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
            await wait_for_confirmation_panel(pilot)

            # Select "Auto LOW/MED"
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("enter")
            await wait_for_idle(pilot)

            # Turn 2: HIGH risk command
            await type_text(pilot, "do it again, mark it as a high risk action though")
            await pilot.press("enter")
            await wait_for_confirmation_panel(pilot)

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
            await wait_for_confirmation_panel(pilot)

            # Select "Auto LOW/MED"
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("enter")
            await wait_for_idle(pilot)

            # Turn 2: HIGH risk command
            await type_text(pilot, "do it again, mark it as a high risk action though")
            await pilot.press("enter")
            await wait_for_confirmation_panel(pilot)

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
