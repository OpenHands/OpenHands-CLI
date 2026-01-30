"""E2E snapshot tests for multi-line mode submission.

These tests capture the user experience for submitting input via multi-line mode.

Flow:
  - Phase 1: App starts and shows initial state
  - Phase 2: User toggles to multi-line mode (Ctrl+L)
  - Phase 3: User types "echo hello world" and presses Enter twice (cursor moves down)
  - Phase 4: User submits with Ctrl+J and conversation completes
"""

from typing import TYPE_CHECKING

from .helpers import type_text, wait_for_app_ready, wait_for_idle


if TYPE_CHECKING:
    from textual.pilot import Pilot


def _create_app(conversation_id):
    """Create an OpenHandsApp instance with mock LLM setup."""
    from openhands.sdk.security.confirmation_policy import NeverConfirm
    from openhands_cli.tui.textual_app import OpenHandsApp

    return OpenHandsApp(
        exit_confirmation=False,
        initial_confirmation_policy=NeverConfirm(),
        resume_conversation_id=conversation_id,
    )


# =============================================================================
# Shared pilot action helpers for reuse across tests
# =============================================================================


async def _wait_for_initial_state(pilot: "Pilot") -> None:
    """Wait for app to initialize and show initial state."""
    await wait_for_app_ready(pilot)


async def _toggle_multiline_mode(pilot: "Pilot") -> None:
    """Toggle to multi-line mode with Ctrl+L."""
    await wait_for_app_ready(pilot)
    await pilot.press("ctrl+l")
    await wait_for_app_ready(pilot)


async def _type_command(pilot: "Pilot") -> None:
    """Toggle to multi-line mode and type the command with new lines.

    Pressing Enter in multi-line mode adds new lines instead of submitting.
    """
    await _toggle_multiline_mode(pilot)
    await type_text(pilot, "echo hello world")
    # Press Enter twice to add new lines
    # (demonstrates Enter doesn't submit in multi-line mode)
    await pilot.press("enter")
    await pilot.press("enter")
    await wait_for_app_ready(pilot)


async def _submit_and_wait_for_completion(pilot: "Pilot") -> None:
    """Toggle to multi-line mode, type command, submit, and wait for completion."""
    await _type_command(pilot)
    await pilot.press("ctrl+j")
    await wait_for_idle(pilot)


# =============================================================================
# Test: Multi-line mode submission flow
# =============================================================================


class TestMultilineModeSubmit:
    """Test multi-line mode submission flow.

    Flow:
    1. App starts and shows initial state
    2. User toggles to multi-line mode (Ctrl+L)
    3. User types "echo hello world"
    4. User submits with Ctrl+J and conversation completes
    """

    def test_phase1_initial_state(self, snap_compare, mock_llm_setup):
        """Phase 1: App starts and shows initial state."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_initial_state
        )

    def test_phase2_multiline_mode_toggled(self, snap_compare, mock_llm_setup):
        """Phase 2: User toggles to multi-line mode with Ctrl+L."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_toggle_multiline_mode
        )

    def test_phase3_command_typed(self, snap_compare, mock_llm_setup):
        """Phase 3: User types 'echo hello world' and presses Enter twice.

        In multi-line mode, Enter adds new lines instead of submitting.
        The cursor moves down, demonstrating that the text was not submitted.
        """
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(app, terminal_size=(120, 40), run_before=_type_command)

    def test_phase4_conversation_completed(self, snap_compare, mock_llm_setup):
        """Phase 4: User submits with Ctrl+J and conversation completes."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_submit_and_wait_for_completion
        )
