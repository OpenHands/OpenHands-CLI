"""E2E snapshot tests for the initial setup flow.

These tests capture the user experience for first-time users who have
not yet configured their agent settings.

Test 1: First-time user sees welcome modal, then exits
  - Phase 1: User is shown welcome modal with LLM settings and Cloud login options
  - Phase 2: User presses escape to cancel and is shown the exit page
  - Phase 3: User presses the exit button and quits the app

Test 2: First-time user chooses LLM settings flow
  - Phase 1: User is shown the welcome modal
  - Phase 2: User clicks "Enter your LLM settings" and sees settings form
  - Phase 3: User fills out the settings form
  - Phase 4: User saves and is shown the landing screen

Test 3: First-time user cancels LLM settings, then returns to welcome modal
  - Phase 1: User sees welcome modal
  - Phase 2: User clicks LLM settings, sees settings form
  - Phase 3: User cancels settings, sees exit modal
  - Phase 4: User cancels exit, returns to welcome modal
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


async def _wait_for_welcome_modal(pilot: "Pilot") -> None:
    """Wait for app to initialize and show welcome modal."""
    await wait_for_app_ready(pilot)


async def _cancel_welcome_modal(pilot: "Pilot") -> None:
    """Press Escape to cancel welcome modal and show exit modal."""
    await wait_for_app_ready(pilot)
    await pilot.press("escape")
    await wait_for_app_ready(pilot)


async def _confirm_exit_from_welcome(pilot: "Pilot") -> None:
    """Cancel welcome modal, then click 'Yes, proceed' to confirm exit."""
    await wait_for_app_ready(pilot)
    await pilot.press("escape")
    await wait_for_app_ready(pilot)
    await pilot.click("#yes")
    await wait_for_app_ready(pilot)


async def _click_llm_settings(pilot: "Pilot") -> None:
    """Click 'Enter your LLM settings' button on welcome modal."""
    await wait_for_app_ready(pilot)
    await pilot.click("#llm_settings_button")
    await wait_for_app_ready(pilot)


async def _fill_settings_form_from_welcome(pilot: "Pilot") -> None:
    """Click LLM settings, then fill out the form."""
    # First click LLM settings button
    await _click_llm_settings(pilot)

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


async def _fill_and_save_settings_from_welcome(pilot: "Pilot") -> None:
    """Fill out settings form and save."""
    await _fill_settings_form_from_welcome(pilot)

    # Click save button
    await pilot.click("#save_button")
    await wait_for_app_ready(pilot)


async def _cancel_settings_from_llm_flow(pilot: "Pilot") -> None:
    """Click LLM settings, then press Escape to cancel."""
    await _click_llm_settings(pilot)
    await pilot.press("escape")
    await wait_for_app_ready(pilot)


async def _cancel_settings_then_return_to_welcome(pilot: "Pilot") -> None:
    """Click LLM settings, cancel, then cancel exit to return to welcome."""
    await _cancel_settings_from_llm_flow(pilot)
    await pilot.click("#no")
    await wait_for_app_ready(pilot)


# =============================================================================
# Test 1: First-time user sees welcome modal, then exits
# =============================================================================


class TestInitialSetupWelcomeModalThenExit:
    """Test 1: First-time user sees welcome modal, then exits.

    Flow:
    1. User is a first time user (no agent configured yet)
    2. User is shown welcome modal with setup options
    3. User cancels and is shown the exit page
    4. User presses the exit button and quits the app
    """

    def test_phase1_welcome_modal(self, snap_compare, first_time_user_setup):
        """Phase 1: First-time user sees the welcome modal."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_welcome_modal
        )

    def test_phase2_exit_page(self, snap_compare, first_time_user_setup):
        """Phase 2: User cancels and is shown the exit page."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_cancel_welcome_modal
        )

    def test_phase3_exit_confirmed(self, snap_compare, first_time_user_setup):
        """Phase 3: User presses the exit button and quits the app."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_confirm_exit_from_welcome
        )


# =============================================================================
# Test 2: First-time user chooses LLM settings flow
# =============================================================================


class TestInitialSetupLLMSettingsFlow:
    """Test 2: First-time user chooses LLM settings flow.

    Flow:
    1. User is a first time user (no agent configured yet)
    2. User is shown the welcome modal
    3. User clicks "Enter your LLM settings" and sees settings form
    4. User fills out the settings form
    5. User saves and is shown the landing screen
    """

    def test_phase1_welcome_modal(self, snap_compare, first_time_user_setup):
        """Phase 1: First-time user sees the welcome modal."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_welcome_modal
        )

    def test_phase2_settings_page(self, snap_compare, first_time_user_setup):
        """Phase 2: User clicks LLM settings and sees settings form."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_click_llm_settings
        )

    def test_phase3_form_filled(self, snap_compare, first_time_user_setup):
        """Phase 3: User fills out the settings form."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_fill_settings_form_from_welcome
        )

    def test_phase4_landing_screen(self, snap_compare, first_time_user_setup):
        """Phase 4: User saves settings and sees the landing screen."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_fill_and_save_settings_from_welcome
        )


# =============================================================================
# Test 3: First-time user cancels LLM settings, then returns to welcome modal
# =============================================================================


class TestInitialSetupCancelSettingsThenReturn:
    """Test 3: First-time user cancels LLM settings, then returns to welcome modal.

    Flow:
    1. User sees welcome modal
    2. User clicks LLM settings, sees settings form
    3. User cancels settings, sees exit modal
    4. User cancels exit, returns to welcome modal
    """

    def test_phase1_welcome_modal(self, snap_compare, first_time_user_setup):
        """Phase 1: First-time user sees the welcome modal."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_wait_for_welcome_modal
        )

    def test_phase2_settings_page(self, snap_compare, first_time_user_setup):
        """Phase 2: User clicks LLM settings and sees settings form."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_click_llm_settings
        )

    def test_phase3_exit_modal(self, snap_compare, first_time_user_setup):
        """Phase 3: User cancels settings and sees exit modal."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_cancel_settings_from_llm_flow
        )

    def test_phase4_back_to_welcome(self, snap_compare, first_time_user_setup):
        """Phase 4: User cancels exit and returns to welcome modal."""
        app = _create_first_time_user_app(first_time_user_setup["conversation_id"])
        assert snap_compare(
            app, terminal_size=(120, 40), run_before=_cancel_settings_then_return_to_welcome
        )
