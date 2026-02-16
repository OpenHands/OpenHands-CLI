"""E2E snapshot tests for select all (Ctrl+A) functionality.

These tests capture the user experience for selecting all text in the input area
using Ctrl+A, followed by deleting the selected content.

Flow:
  - Phase 1: App starts and shows initial state
  - Phase 2: User types a large amount of text
  - Phase 3: User presses Ctrl+A to select all text
  - Phase 4: User presses Delete to delete all selected text
"""

from typing import TYPE_CHECKING

from .helpers import type_text, wait_for_app_ready


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


async def _type_large_text(pilot: "Pilot") -> None:
    """Type a large amount of text into the input field."""
    await wait_for_app_ready(pilot)
    # Type a large text that wraps to multiple lines
    await type_text(
        pilot,
        "This is a large amount of text that should wrap to multiple "
        "lines when typed into the input area. "
        "It contains multiple sentences to ensure we have enough content "
        "to demonstrate the select all functionality. "
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
    )


async def _select_all_text(pilot: "Pilot") -> None:
    """Type text and then press Ctrl+A to select all."""
    await _type_large_text(pilot)
    # Press Ctrl+A to select all
    await pilot.press("ctrl+a")
    await wait_for_app_ready(pilot)


async def _delete_selected_text(pilot: "Pilot") -> None:
    """Type text, select all with Ctrl+A, then press Delete to delete."""
    await _select_all_text(pilot)
    # Press Delete to delete the selected text
    await pilot.press("delete")
    await wait_for_app_ready(pilot)


# =============================================================================
# Test: Select all (Ctrl+A) functionality
# =============================================================================


class TestSelectAllFunctionality:
    """Test select all (Ctrl+A) functionality.

    Flow:
    1. App starts and shows initial state
    2. User types a large amount of text
    3. User presses Ctrl+A to select all text
    4. User presses Delete to delete all selected text
    """

    def test_phase1_initial_state(self, snap_compare, mock_llm_setup):
        """Phase 1: App starts and shows initial state."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_initial_state
        )

    def test_phase2_large_text_typed(self, snap_compare, mock_llm_setup):
        """Phase 2: User types a large amount of text."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(app, terminal_size=(120, 40), run_before=_type_large_text)

    def test_phase3_all_text_selected(self, snap_compare, mock_llm_setup):
        """Phase 3: User presses Ctrl+A to select all text."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(app, terminal_size=(120, 40), run_before=_select_all_text)

    def test_phase4_text_deleted(self, snap_compare, mock_llm_setup):
        """Phase 4: User presses Delete to delete all selected text."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_delete_selected_text
        )
