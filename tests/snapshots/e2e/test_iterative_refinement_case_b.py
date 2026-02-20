"""E2E snapshot tests for iterative refinement flow (Case B - 1 iteration).

This test validates a shorter iterative refinement flow where the critic
triggers only one refinement iteration before the task is considered complete:

Trajectory: cli447_hi_followup_iterative_case_b
- User sends "hi"
- Agent responds with greeting (critic score: 0.41 < threshold)
- System sends refinement message (iteration 1/3)
- Agent responds with clarification (critic score: 0.85 > threshold)
- Task complete (no more refinement needed)

The test captures snapshots at key phases to verify:
1. Initial greeting exchange
2. Refinement message after low critic score
3. Final response after refinement (score above threshold)
"""

from typing import TYPE_CHECKING

import pytest

from .helpers import type_text, wait_for_app_ready, wait_for_idle


if TYPE_CHECKING:
    from textual.pilot import Pilot


def _create_app(conversation_id, *, enable_refinement: bool = True):
    """Create an OpenHandsApp instance with iterative refinement enabled.

    Args:
        conversation_id: UUID for the conversation
        enable_refinement: Whether to enable iterative refinement mode

    Note:
        Critic settings are configured via the mock_llm_with_critic fixture
        which patches CliSettings.load() to return the desired settings.
    """
    from openhands.sdk.security.confirmation_policy import NeverConfirm
    from openhands_cli.tui.textual_app import OpenHandsApp

    return OpenHandsApp(
        exit_confirmation=False,
        initial_confirmation_policy=NeverConfirm(),
        resume_conversation_id=conversation_id,
    )


# =============================================================================
# Shared pilot action helpers
# =============================================================================


async def _wait_for_initial_state(pilot: "Pilot") -> None:
    """Phase 1: Wait for app to initialize and show initial state."""
    await wait_for_app_ready(pilot)


async def _type_hi_and_wait_for_response(pilot: "Pilot") -> None:
    """Phase 2: Type 'hi' and wait for agent's first response.

    This triggers the first critic evaluation which should score low (0.41)
    and trigger iterative refinement.
    """
    await wait_for_app_ready(pilot)
    await type_text(pilot, "hi")
    await pilot.press("enter")
    await wait_for_idle(pilot, timeout=30)

    # Scroll to ensure we see the response
    await pilot.press("end")
    await pilot.wait_for_scheduled_animations()


async def _wait_for_refinement_complete(pilot: "Pilot") -> None:
    """Phase 3: Wait for refinement to complete.

    After the first refinement message, the agent responds with a higher
    score (0.85) which exceeds the threshold (0.8), so no more refinement
    is needed.
    """
    await _type_hi_and_wait_for_response(pilot)

    # Wait for refinement message and final agent response
    await wait_for_idle(pilot, timeout=30)

    # Scroll to end to see final state
    await pilot.press("end")
    await pilot.wait_for_scheduled_animations()


# =============================================================================
# Test: Iterative refinement flow (Case B - 1 iteration)
# =============================================================================


class TestIterativeRefinementCaseB:
    """Test iterative refinement flow with only 1 refinement iteration.

    Flow:
    1. App starts and shows initial state
    2. User types "hi", agent responds, critic scores low (0.41)
    3. Refinement triggered - iteration 1/3
    4. Agent clarifies, critic scores above threshold (0.85 > 0.8)
    5. Task complete - no more refinement needed
    """

    @pytest.mark.parametrize(
        "mock_llm_with_critic",
        ["cli447_hi_followup_iterative_case_b"],
        indirect=True,
    )
    def test_phase1_initial_state(self, snap_compare, mock_llm_with_critic):
        """Phase 1: App starts and shows initial state with refinement mode enabled."""
        app = _create_app(mock_llm_with_critic["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_initial_state
        )

    @pytest.mark.parametrize(
        "mock_llm_with_critic",
        ["cli447_hi_followup_iterative_case_b"],
        indirect=True,
    )
    def test_phase2_first_response_with_low_critic_score(
        self, snap_compare, mock_llm_with_critic
    ):
        """Phase 2: User types 'hi', agent responds, critic evaluates low.

        The critic score (0.41) is below the threshold (0.8), which should
        trigger a refinement message.
        """
        app = _create_app(mock_llm_with_critic["conversation_id"])
        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=_type_hi_and_wait_for_response,
        )

    @pytest.mark.parametrize(
        "mock_llm_with_critic",
        ["cli447_hi_followup_iterative_case_b"],
        indirect=True,
    )
    def test_phase3_refinement_complete_after_one_iteration(
        self, snap_compare, mock_llm_with_critic
    ):
        """Phase 3: Refinement completes after one iteration.

        After the refinement message, the agent responds with clarification.
        The new critic score (0.85) exceeds the threshold (0.8), so the
        refinement loop completes after just one iteration.
        """
        app = _create_app(mock_llm_with_critic["conversation_id"])
        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=_wait_for_refinement_complete,
        )
