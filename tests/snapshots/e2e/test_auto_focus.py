"""E2E snapshot test for auto-focus behavior when typing.

This test validates that when a user types a printable character while
focus is not on the input field, the character is preserved in the
input field after auto-focus.

This verifies the fix for the UX issue where typing a character while
focus was elsewhere would move focus to the input field but lose
the character.
"""

from textual.pilot import Pilot

from .helpers import wait_for_app_ready


class TestAutoFocusPreservesCharacter:
    """Test that auto-focus preserves typed character."""

    def test_auto_focus_preserves_typed_character(self, snap_compare, mock_llm_setup):
        """Test that typing a character when focus is elsewhere auto-focuses input.

        This verifies the fix for the UX issue where typing a character while focus
        was elsewhere would move focus to the input field but lose the character.

        Steps:
        1. Start the app with a mock LLM
        2. Wait for app to be ready
        3. Press Tab to move focus away from input field
        4. Type a character 'h'
        5. Assert character appears in input and focus moved to input
        """
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp

        async def type_with_focus_elsewhere(pilot: Pilot):
            """Type a character when focus is not on the input field."""
            await wait_for_app_ready(pilot)

            # Press Tab to move focus away from input
            # Then type a character - should auto-focus input + preserve 'h'
            await pilot.press("tab")
            await pilot.press("h")

        # Use fixed conversation ID from fixture for deterministic snapshots
        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=NeverConfirm(),
            resume_conversation_id=mock_llm_setup["conversation_id"],
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=type_with_focus_elsewhere,
        )
