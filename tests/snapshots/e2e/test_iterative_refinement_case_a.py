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

The test captures snapshots at key phases to verify:
1. Initial greeting exchange
2. Refinement message display
3. Tool execution during refinement
4. Final completion state
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

    This triggers the first critic evaluation which should score low
    and trigger iterative refinement.
    """
    await wait_for_app_ready(pilot)
    await type_text(pilot, "hi")
    await pilot.press("enter")
    await wait_for_idle(pilot, timeout=30)

    # Scroll to ensure we see the refinement message
    await pilot.press("end")
    await pilot.wait_for_scheduled_animations()


async def _wait_for_refinement_iteration_1(pilot: "Pilot") -> None:
    """Phase 3: Wait for first refinement iteration to complete.

    The system should send a refinement message and the agent should respond.
    """
    await _type_hi_and_wait_for_response(pilot)

    # Wait for refinement message and agent's response
    await wait_for_idle(pilot, timeout=30)

    # Scroll to end
    await pilot.press("end")
    await pilot.wait_for_scheduled_animations()


async def _wait_for_refinement_iteration_2(pilot: "Pilot") -> None:
    """Phase 4: Wait for second refinement iteration.

    The agent may use tools (file_editor, terminal) during this iteration.
    """
    await _wait_for_refinement_iteration_1(pilot)

    # Wait for second iteration's agent response
    await wait_for_idle(pilot, timeout=30)

    # Scroll to end
    await pilot.press("end")
    await pilot.wait_for_scheduled_animations()


async def _wait_for_refinement_complete(pilot: "Pilot") -> None:
    """Phase 5: Wait for all refinement iterations to complete.

    The agent should eventually call finish when the task is complete.
    """
    await _wait_for_refinement_iteration_2(pilot)

    # Wait for final iteration and finish
    await wait_for_idle(pilot, timeout=30)

    # Scroll to end to see final state
    await pilot.press("end")
    await pilot.wait_for_scheduled_animations()


# =============================================================================
# Test: Iterative refinement flow (Case A - 3 iterations)
# =============================================================================


class TestIterativeRefinementCaseA:
    """Test iterative refinement flow with 3 refinement iterations.

    Flow:
    1. App starts and shows initial state
    2. User types "hi", agent responds, critic scores low (0.38)
    3. Refinement triggered - iteration 1/3
    4. Agent clarifies, critic scores higher (0.82)
    5. Refinement continues - iteration 2/3 (agent uses tools)
    6. Agent responds, critic scores (0.88)
    7. Refinement continues - iteration 3/3
    8. Agent calls finish, refinement complete
    """

    @pytest.mark.parametrize(
        "mock_llm_with_critic",
        ["cli447_hi_followup_iterative_case_a"],
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
        ["cli447_hi_followup_iterative_case_a"],
        indirect=True,
    )
    def test_phase2_first_response_with_low_critic_score(
        self, snap_compare, mock_llm_with_critic
    ):
        """Phase 2: User types 'hi', agent responds, critic evaluates low.

        The critic score (0.38) is below the threshold (0.9), which should
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
        ["cli447_hi_followup_iterative_case_a"],
        indirect=True,
    )
    def test_phase3_refinement_iteration_1(self, snap_compare, mock_llm_with_critic):
        """Phase 3: First refinement iteration - system prompts agent to review.

        After the low critic score, the system sends a refinement message
        asking the agent to verify requirements and complete the task.
        """
        app = _create_app(mock_llm_with_critic["conversation_id"])
        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=_wait_for_refinement_iteration_1,
        )

    @pytest.mark.parametrize(
        "mock_llm_with_critic",
        ["cli447_hi_followup_iterative_case_a"],
        indirect=True,
    )
    def test_phase4_refinement_iteration_2(self, snap_compare, mock_llm_with_critic):
        """Phase 4: Second refinement iteration - agent may use tools.

        The agent explores the environment using file_editor and terminal
        to better understand and complete the task.
        """
        app = _create_app(mock_llm_with_critic["conversation_id"])
        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=_wait_for_refinement_iteration_2,
        )

    @pytest.mark.parametrize(
        "mock_llm_with_critic",
        ["cli447_hi_followup_iterative_case_a"],
        indirect=True,
    )
    def test_phase5_refinement_complete(self, snap_compare, mock_llm_with_critic):
        """Phase 5: Refinement complete - agent calls finish.

        After 3 iterations, the agent determines the task is complete
        and calls the finish tool.
        """
        app = _create_app(mock_llm_with_critic["conversation_id"])
        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=_wait_for_refinement_complete,
        )
