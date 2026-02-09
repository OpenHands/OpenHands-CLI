"""E2E snapshot tests for confirmation mode.

This test validates the confirmation mode flow with ConfirmRisky policy:
1. User types "echo hello world" (LOW risk) - shows confirmation panel
2. User selects "Auto LOW/MED" - sets ConfirmRisky policy, action proceeds
3. User asks to repeat with HIGH risk - shows confirmation panel (HIGH > threshold)
4. User confirms HIGH risk action - sees result
5. User asks once more with LOW risk - auto-proceeds (no confirmation needed)

The test uses the 'confirmation_mode' trajectory which simulates
a conversation where the user triggers actions at different risk levels.
"""

from typing import TYPE_CHECKING

import pytest

from .helpers import type_text, wait_for_app_ready, wait_for_idle


if TYPE_CHECKING:
    from textual.pilot import Pilot


def _create_app(conversation_id):
    """Create an OpenHandsApp instance with AlwaysConfirm policy.

    AlwaysConfirm policy requires user confirmation for every action,
    which lets us test the confirmation panel UI. The user can then
    select "Auto LOW/MED" to switch to ConfirmRisky policy.
    """
    from openhands.sdk.security.confirmation_policy import AlwaysConfirm
    from openhands_cli.tui.textual_app import OpenHandsApp

    return OpenHandsApp(
        exit_confirmation=False,
        initial_confirmation_policy=AlwaysConfirm(),
        resume_conversation_id=conversation_id,
    )


# =============================================================================
# Shared pilot action helpers for reuse across tests
# =============================================================================


async def _wait_for_initial_state(pilot: "Pilot") -> None:
    """Phase 1: Wait for app to initialize and show initial state."""
    await wait_for_app_ready(pilot)


async def _type_first_message_and_navigate_to_auto(pilot: "Pilot") -> None:
    """Phase 2: Type message and navigate to 'Auto LOW/MED' option.

    Shows confirmation panel with 'Auto LOW/MED' highlighted, ready to click.
    Options order: Yes (0), No (1), Always (2), Auto LOW/MED (3)
    """
    await wait_for_app_ready(pilot)
    await type_text(pilot, "echo hello world")
    await pilot.press("enter")
    await wait_for_idle(pilot, timeout=10)

    # Navigate to "Auto LOW/MED" (4th option, index 3)
    await pilot.press("down")  # No
    await pilot.press("down")  # Always
    await pilot.press("down")  # Auto LOW/MED
    await pilot.wait_for_scheduled_animations()


async def _select_auto_low_med(pilot: "Pilot") -> None:
    """Phase 3: Select 'Auto LOW/MED' option to set ConfirmRisky policy."""
    await _type_first_message_and_navigate_to_auto(pilot)

    # Press enter to select "Auto LOW/MED"
    await pilot.press("enter")
    await wait_for_idle(pilot, timeout=10)


async def _type_second_message_high_risk(pilot: "Pilot") -> None:
    """Phase 4: Type message that triggers HIGH risk action.

    After selecting Auto LOW/MED, HIGH risk actions still require confirmation.
    """
    await _select_auto_low_med(pilot)

    # Type the second message asking for HIGH risk action
    await type_text(pilot, "do it again, mark it as a high risk action though")
    await pilot.press("enter")
    await wait_for_idle(pilot, timeout=10)


async def _confirm_high_risk_action(pilot: "Pilot") -> None:
    """Phase 5: Confirm the HIGH risk action (select 'Yes')."""
    await _type_second_message_high_risk(pilot)

    # Press enter to accept the confirmation (first option is "Yes")
    await pilot.press("enter")
    await wait_for_idle(pilot, timeout=10)


async def _type_third_message_low_risk_auto_proceeds(pilot: "Pilot") -> None:
    """Phase 6: Type third message with LOW risk - auto-proceeds without confirmation.

    With ConfirmRisky policy active, LOW risk actions auto-proceed.
    """
    await _confirm_high_risk_action(pilot)

    # Type the third message asking for a LOW risk action
    await type_text(pilot, "once more, don't mark it as high risk this time")
    await pilot.press("enter")
    await wait_for_idle(pilot, timeout=10)

    # Scroll to end for consistent snapshot
    await pilot.press("end")
    await pilot.wait_for_scheduled_animations()


# =============================================================================
# Test: Confirmation mode flow with ConfirmRisky
# =============================================================================


class TestConfirmationMode:
    """Test confirmation mode flow demonstrating ConfirmRisky policy.

    Flow:
    1. App starts showing initial state
    2. User types "echo hello world" - confirmation panel appears (AlwaysConfirm)
    3. User selects "Auto LOW/MED" - switches to ConfirmRisky policy, action proceeds
    4. User types HIGH risk action - confirmation panel appears (HIGH > threshold)
    5. User confirms HIGH risk action - sees result
    6. User types LOW risk action - auto-proceeds (no confirmation with ConfirmRisky)
    """

    # Use `indirect` to pass 'confirmation_mode' to the fixture, not the test
    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["confirmation_mode"], indirect=True
    )
    def test_phase1_initial_state(self, snap_compare, mock_llm_with_trajectory):
        """Phase 1: App starts and shows initial state."""
        app = _create_app(mock_llm_with_trajectory["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_initial_state
        )

    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["confirmation_mode"], indirect=True
    )
    def test_phase2_confirmation_panel_auto_low_med_highlighted(
        self, snap_compare, mock_llm_with_trajectory
    ):
        """Phase 2: Confirmation panel with 'Auto LOW/MED' option highlighted.

        User types first message, confirmation panel appears, and user navigates
        to 'Auto LOW/MED' option (ready to click).
        """
        app = _create_app(mock_llm_with_trajectory["conversation_id"])
        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=_type_first_message_and_navigate_to_auto,
        )

    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["confirmation_mode"], indirect=True
    )
    def test_phase3_auto_low_med_selected(self, snap_compare, mock_llm_with_trajectory):
        """Phase 3: User selects 'Auto LOW/MED', action proceeds.

        This switches the policy to ConfirmRisky which auto-approves LOW/MEDIUM risk.
        """
        app = _create_app(mock_llm_with_trajectory["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_select_auto_low_med
        )

    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["confirmation_mode"], indirect=True
    )
    def test_phase4_high_risk_confirmation_panel(
        self, snap_compare, mock_llm_with_trajectory
    ):
        """Phase 4: User asks for HIGH risk action, confirmation panel appears.

        Even with ConfirmRisky policy, HIGH risk actions require confirmation.
        """
        app = _create_app(mock_llm_with_trajectory["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_type_second_message_high_risk
        )

    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["confirmation_mode"], indirect=True
    )
    def test_phase5_high_risk_action_confirmed(
        self, snap_compare, mock_llm_with_trajectory
    ):
        """Phase 5: User confirms HIGH risk action, sees the result."""
        app = _create_app(mock_llm_with_trajectory["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_confirm_high_risk_action
        )

    @pytest.mark.parametrize(
        "mock_llm_with_trajectory", ["confirmation_mode"], indirect=True
    )
    def test_phase6_low_risk_auto_proceeds(
        self, snap_compare, mock_llm_with_trajectory
    ):
        """Phase 6: User asks for LOW risk action - auto-proceeds without confirmation.

        With ConfirmRisky policy, LOW risk actions don't need confirmation.
        Final state shows complete conversation.
        """
        app = _create_app(mock_llm_with_trajectory["conversation_id"])
        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=_type_third_message_low_risk_auto_proceeds,
        )
