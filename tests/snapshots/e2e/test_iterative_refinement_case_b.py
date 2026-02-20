"""E2E snapshot tests for iterative refinement flow (Case B - 1 iteration).

This test validates a shorter iterative refinement flow where the critic
triggers only one refinement iteration before the task is considered complete:

Trajectory: cli447_hi_followup_iterative_case_b
- User sends "hi"
- Agent responds with greeting (critic score: 0.41 < threshold)
- System sends refinement message (iteration 1/3)
- Agent responds with clarification (critic score: 0.85 > threshold)
- Task complete (no more refinement needed)

The test captures snapshots at initial state and final completion state.
"""

from typing import TYPE_CHECKING

import pytest

from .helpers import type_text, wait_for_app_ready, wait_for_idle


if TYPE_CHECKING:
    from textual.pilot import Pilot


def _create_app(conversation_id):
    """Create an OpenHandsApp instance with iterative refinement enabled."""
    from openhands.sdk.security.confirmation_policy import NeverConfirm
    from openhands_cli.tui.textual_app import OpenHandsApp

    return OpenHandsApp(
        exit_confirmation=False,
        initial_confirmation_policy=NeverConfirm(),
        resume_conversation_id=conversation_id,
    )


async def _wait_for_initial_state(pilot: "Pilot") -> None:
    """Wait for app to initialize and show initial state."""
    await wait_for_app_ready(pilot)


async def _type_hi_and_wait_for_complete(pilot: "Pilot") -> None:
    """Type 'hi' and wait for refinement to complete."""
    await wait_for_app_ready(pilot)
    await type_text(pilot, "hi")
    await pilot.press("enter")
    await wait_for_idle(pilot, timeout=30)
    await pilot.press("end")
    await pilot.wait_for_scheduled_animations()


class TestIterativeRefinementCaseB:
    """Test iterative refinement flow with 1 refinement iteration."""

    @pytest.mark.parametrize(
        "mock_llm_with_critic",
        ["cli447_hi_followup_iterative_case_b"],
        indirect=True,
    )
    def test_initial_state(self, snap_compare, mock_llm_with_critic):
        """App shows initial state with refinement mode enabled."""
        app = _create_app(mock_llm_with_critic["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_initial_state
        )

    @pytest.mark.parametrize(
        "mock_llm_with_critic",
        ["cli447_hi_followup_iterative_case_b"],
        indirect=True,
    )
    def test_refinement_complete(self, snap_compare, mock_llm_with_critic):
        """Complete refinement flow after one iteration."""
        app = _create_app(mock_llm_with_critic["conversation_id"])
        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=_type_hi_and_wait_for_complete,
        )
