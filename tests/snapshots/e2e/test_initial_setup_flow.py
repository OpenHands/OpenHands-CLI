"""E2E snapshot tests for the initial setup flow.

These tests capture the user experience for first-time users who have
not yet configured their agent settings.

Test 1: First-time user cancels settings, then exits
  - Phase 1: User is shown settings page
  - Phase 2: User cancels and is shown the exit page
  - Phase 3: User presses the exit button and quits the app

Test 2: First-time user cancels settings, cancels exit, fills form, saves
  - Phase 1: User is shown the settings page
  - Phase 2: User cancels and is shown the exit page
  - Phase 3: User cancels on the exit screen and is returned to settings page
  - Phase 4: User fills out the settings form
  - Phase 5: User saves and is shown the landing screen
"""

from typing import TYPE_CHECKING

from .helpers import type_text, wait_for_app_ready


if TYPE_CHECKING:
    from textual.pilot import Pilot


def _create_first_time_user_app(conversation_id):
    """Create an OpenHandsApp instance for a first-time user."""
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


async def _wait_for_settings_page(pilot: "Pilot") -> None:
    """Wait for app to initialize and show settings screen."""
    await wait_for_app_ready(pilot)


async def _cancel_settings(pilot: "Pilot") -> None:
    """Press Escape to cancel settings and show exit modal."""
    await wait_for_app_ready(pilot)
    await pilot.press("escape")
    await wait_for_app_ready(pilot)


async def _confirm_exit(pilot: "Pilot") -> None:
    """Click 'Yes, proceed' to confirm exit."""
    await wait_for_app_ready(pilot)
    await pilot.press("escape")
    await wait_for_app_ready(pilot)
    await pilot.click("#yes")
    await wait_for_app_ready(pilot)


async def _cancel_exit_return_to_settings(pilot: "Pilot") -> None:
    """Cancel settings, then cancel exit to return to settings."""
    await wait_for_app_ready(pilot)
    await pilot.press("escape")
    await wait_for_app_ready(pilot)
    await pilot.click("#no")
    await wait_for_app_ready(pilot)


async def _fill_settings_form(pilot: "Pilot") -> None:
    """Cancel settings, cancel exit, return to settings, then fill out the form."""
    # First return to settings
    await _cancel_exit_return_to_settings(pilot)

    # Select provider (openai)
    await pilot.click("#provider_select")
    await wait_for_app_ready(pilot)
    await type_text(pilot, "openai")  # Type to search
    await pilot.press("enter")
    await wait_for_app_ready(pilot)

    # Select model (gpt-4o-mini)
    await pilot.click("#model_select")
    await wait_for_app_ready(pilot)
    await type_text(pilot, "gpt-4o-mini")
    await pilot.press("enter")
    await wait_for_app_ready(pilot)

    # Scroll down to see the API key field (it's in a modal screen)
    api_key_input = pilot.app.screen.query_one("#api_key_input")
    api_key_input.scroll_visible(animate=False)
    await wait_for_app_ready(pilot)

    # Enter API key
    await pilot.click("#api_key_input")
    await wait_for_app_ready(pilot)
    await type_text(pilot, "sk-test-key-12345")
    await wait_for_app_ready(pilot)


async def _fill_and_save_settings(pilot: "Pilot") -> None:
    """Fill out settings form and save."""
    await _fill_settings_form(pilot)

    # Click save button
    await pilot.click("#save_button")
    await wait_for_app_ready(pilot)


# =============================================================================
# Test 1: First-time user cancels settings, then exits
# =============================================================================


class TestInitialSetupCancelThenExit:
    """Test 1: First-time user cancels settings, then exits.

    Flow:
    1. User is a first time user (no agent configured yet)
    2. User is shown settings page
    3. User cancels and is shown the exit page
    4. User presses the exit button and quits the app
    """

    def test_phase1_settings_page(self, snap_compare, first_time_user_setup):
        """Phase 1: First-time user sees the settings page."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_settings_page
        )

    def test_phase2_exit_page(self, snap_compare, first_time_user_setup):
        """Phase 2: User cancels and is shown the exit page."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(app, terminal_size=(120, 40), run_before=_cancel_settings)

    def test_phase3_exit_confirmed(self, snap_compare, first_time_user_setup):
        """Phase 3: User presses the exit button and quits the app."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(app, terminal_size=(120, 40), run_before=_confirm_exit)


# =============================================================================
# Test 2: First-time user cancels settings, cancels exit, returns to settings
# =============================================================================


class TestInitialSetupCancelThenReturn:
    """Test 2: First-time user cancels settings, cancels exit, fills form, saves.

    Flow:
    1. User is a first time user (no agent configured yet)
    2. User is shown the settings page
    3. User cancels and is shown the exit page
    4. User cancels on the exit screen and is returned to the settings page
    5. User fills out the settings form
    6. User saves and is shown the landing screen
    """

    def test_phase1_settings_page(self, snap_compare, first_time_user_setup):
        """Phase 1: First-time user sees the settings page."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_settings_page
        )

    def test_phase2_exit_page(self, snap_compare, first_time_user_setup):
        """Phase 2: User cancels and is shown the exit page."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(app, terminal_size=(120, 40), run_before=_cancel_settings)

    def test_phase3_returned_to_settings(self, snap_compare, first_time_user_setup):
        """Phase 3: User cancels on exit screen and is returned to settings."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_cancel_exit_return_to_settings
        )

    def test_phase4_form_filled(self, snap_compare, first_time_user_setup):
        """Phase 4: User fills out the settings form."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_fill_settings_form
        )

    def test_phase5_landing_screen(self, snap_compare, first_time_user_setup):
        """Phase 5: User saves settings and sees the landing screen."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_fill_and_save_settings
        )
