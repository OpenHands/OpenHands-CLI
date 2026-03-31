"""E2E snapshot tests for iterative refinement flow (Case A - 3 iterations).

This test validates the iterative refinement flow where the critic triggers
multiple refinement iterations before the task is considered complete:

Trajectory: cli447_hi_followup_iterative_case_a
- User sends "hi"
- Agent responds with greeting (critic score: 0.38 < threshold)
- System sends refinement message (iteration 1/3)
- Agent responds with clarification (critic score: 0.82)
- System sends refinement message (iteration 2/3)
- Agent uses tools (file_editor, terminal)
- Agent responds (critic score: 0.88)
- System sends refinement message (iteration 3/3)
- Agent calls finish (critic score: 0.83 > threshold)

The test captures snapshots at initial state and final completion state.
Intermediate phases execute too quickly to produce distinct visual states.
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
    """Type 'hi' and wait for all refinement iterations to complete."""
    await wait_for_app_ready(pilot)
    await type_text(pilot, "hi")
    await pilot.press("enter")
    await wait_for_idle(pilot, timeout=60)
    await pilot.press("end")
    await pilot.wait_for_scheduled_animations()


class TestIterativeRefinementCaseA:
    """Test iterative refinement flow with 3 refinement iterations."""

    @pytest.mark.parametrize(
        "mock_llm_with_critic",
        ["cli447_hi_followup_iterative_case_a"],
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
        ["cli447_hi_followup_iterative_case_a"],
        indirect=True,
    )
    def test_refinement_complete(self, snap_compare, mock_llm_with_critic):
        """Complete iterative refinement flow ending with agent finish."""
        app = _create_app(mock_llm_with_critic["conversation_id"])
        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=_type_hi_and_wait_for_complete,
        )
