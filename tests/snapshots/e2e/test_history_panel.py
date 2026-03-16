"""E2E snapshot tests for history panel and conversation switching.

Test flow:
1. Open app and run /history command (shows current conversation)
2. Run "echo hello world" (first conversation)
3. Type /new command (new conversation splash)
4. Run "second conversation message" (second conversation)
5. Click previous conversation in history panel (switching)
6. Wait for previous conversation to load (loaded conversation)
"""

from typing import TYPE_CHECKING

from .helpers import type_text, wait_for_app_ready, wait_for_idle


if TYPE_CHECKING:
    from textual.pilot import Pilot


def _create_app(conversation_id):
    """Create an OpenHandsApp instance for testing."""
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


async def _open_history_panel(pilot: "Pilot") -> None:
    """Phase 1: Open app and run /history command."""
    await wait_for_app_ready(pilot)

    # Open history panel
    await type_text(pilot, "/history")
    # First enter selects from dropdown, second enter executes /history
    await pilot.press("enter")
    await pilot.press("enter")
    await wait_for_idle(pilot)
    await pilot.wait_for_scheduled_animations()


async def _run_first_conversation(pilot: "Pilot") -> None:
    """Phase 2: Open history panel and run first conversation."""
    await _open_history_panel(pilot)

    # Run first conversation
    await type_text(pilot, "echo hello world")
    await pilot.press("enter")
    await wait_for_idle(pilot)

    # Ensure consistent scroll position by scrolling to end
    # This makes the snapshot deterministic across different environments
    # Use scroll_end directly on the scroll view instead of pilot.press("end")
    # which may be captured by the focused input widget
    scroll_view = pilot.app.query_one("#scroll_view")
    scroll_view.scroll_end(animate=False)
    await pilot.wait_for_scheduled_animations()


async def _start_new_conversation(pilot: "Pilot") -> None:
    """Phase 3: Run first conversation, then start new conversation with /new."""
    await _run_first_conversation(pilot)

    # Start new conversation
    await type_text(pilot, "/new")
    # First enter selects from dropdown, second enter executes /new
    await pilot.press("enter")
    await pilot.press("enter")
    await wait_for_idle(pilot)
    await pilot.wait_for_scheduled_animations()


async def _run_second_conversation(pilot: "Pilot") -> None:
    """Phase 4: Start new conversation, then run second conversation."""
    await _start_new_conversation(pilot)

    # Run second conversation
    await type_text(pilot, "second conversation message")
    await pilot.press("enter")
    await wait_for_idle(pilot)


async def _click_previous_conversation(pilot: "Pilot") -> None:
    """Phase 5: Run second conversation, then click previous conversation."""
    from openhands_cli.tui.panels.history_side_panel import HistoryItem

    await _run_second_conversation(pilot)

    # Click on the previous (older) conversation
    # The history panel shows conversations with the newest first,
    # so we want to click on the second item (index 1) which is the older one
    history_items = list(pilot.app.query(HistoryItem))
    if len(history_items) >= 2:
        # Click on the second item (the older conversation)
        # Use on_click() method directly since pilot.click requires a selector
        history_items[1].on_click()
        await pilot.wait_for_scheduled_animations()


async def _wait_for_conversation_load(pilot: "Pilot") -> None:
    """Phase 6: Click previous conversation, then wait for it to load."""
    await _click_previous_conversation(pilot)

    # Wait for conversation switch to complete
    await wait_for_idle(pilot)
    await pilot.wait_for_scheduled_animations()


# =============================================================================
# Test: History panel and conversation switching flow
# =============================================================================


class TestHistoryPanelFlow:
    """Test history panel and conversation switching flow.

    Flow:
    1. Open app and run /history command (shows current conversation)
    2. Run "echo hello world" (first conversation)
    3. Type /new command (new conversation splash)
    4. Run "second conversation message" (second conversation)
    5. Click previous conversation in history panel (switching)
    6. Wait for previous conversation to load (loaded conversation)
    """

    def test_phase1_history_panel(
        self, snap_compare, mock_llm_setup, e2e_test_environment
    ):
        """Phase 1: Open app and run /history command showing current conversation."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_open_history_panel
        )

    def test_phase2_first_conversation(
        self, snap_compare, mock_llm_setup, e2e_test_environment
    ):
        """Phase 2: Run first conversation message."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_run_first_conversation
        )

    def test_phase3_new_conversation(
        self, snap_compare, mock_llm_setup, e2e_test_environment
    ):
        """Phase 3: Type /new command to start a new conversation."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_start_new_conversation
        )

    def test_phase4_second_conversation(
        self, snap_compare, mock_llm_setup, e2e_test_environment
    ):
        """Phase 4: Run second conversation message."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_run_second_conversation
        )

    def test_phase5_click_previous_conversation(
        self, snap_compare, mock_llm_setup, e2e_test_environment
    ):
        """Phase 5: Click on previous conversation in history panel."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_click_previous_conversation
        )

    def test_phase6_conversation_loaded(
        self, snap_compare, mock_llm_setup, e2e_test_environment
    ):
        """Phase 6: Wait for previous conversation to fully load."""
        app = _create_app(mock_llm_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_conversation_load
        )
