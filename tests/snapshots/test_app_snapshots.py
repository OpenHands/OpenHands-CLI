"""Snapshot tests for OpenHands CLI Textual application.

These tests use pytest-textual-snapshot to capture and compare SVG screenshots
of the application at various states. This helps detect visual regressions
and provides a way to debug the UI.

To update snapshots when intentional changes are made:
    pytest tests/snapshots/ --snapshot-update

To run these tests:
    pytest tests/snapshots/

For more information:
    https://github.com/Textualize/pytest-textual-snapshot
"""

from unittest.mock import patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Footer, Static

from openhands_cli.tui.modals.exit_modal import ExitConfirmationModal
from openhands_cli.tui.widgets.input_field import InputField


# Note: pytest-textual-snapshot tests must be synchronous.
# The snap_compare fixture handles async internally via Textual's run_test().


class TestExitModalSnapshots:
    """Snapshot tests for the ExitConfirmationModal."""

    @pytest.fixture
    def exit_modal_app(self):
        """Create a simple app that hosts the exit confirmation modal."""

        class ExitModalTestApp(App):
            CSS = """
            Screen {
                align: center middle;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Background content")
                yield Footer()

            def on_mount(self) -> None:
                self.push_screen(ExitConfirmationModal())

        return ExitModalTestApp()

    def test_exit_modal_initial_state(self, snap_compare, exit_modal_app):
        """Snapshot test for exit confirmation modal initial state."""
        assert snap_compare(exit_modal_app, terminal_size=(80, 24))

    def test_exit_modal_with_focus_on_yes(self, snap_compare):
        """Snapshot test for exit modal with focus on Yes button."""

        class ExitModalFocusTestApp(App):
            CSS = """
            Screen {
                align: center middle;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Background content")
                yield Footer()

            def on_mount(self) -> None:
                self.push_screen(ExitConfirmationModal())

        assert snap_compare(
            ExitModalFocusTestApp(),
            terminal_size=(80, 24),
            press=["tab"],  # Focus on Yes button
        )


class TestInputFieldSnapshots:
    """Snapshot tests for the InputField widget."""

    @pytest.fixture
    def input_field_app(self):
        """Create an app that hosts the InputField widget for testing."""

        class InputFieldTestApp(App):
            CSS = """
            Screen {
                layout: vertical;
            }
            #test_input {
                dock: bottom;
                height: auto;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Test Application Content", id="content")
                yield InputField(placeholder="Type your message...", id="test_input")
                yield Footer()

        return InputFieldTestApp()

    def test_input_field_single_line_mode(self, snap_compare, input_field_app):
        """Snapshot test for input field in single-line mode."""
        assert snap_compare(input_field_app, terminal_size=(80, 24))

    def test_input_field_with_text(self, snap_compare):
        """Snapshot test for input field with some text typed."""

        class InputFieldWithTextApp(App):
            CSS = """
            Screen {
                layout: vertical;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Test Application Content", id="content")
                yield InputField(placeholder="Type your message...", id="test_input")
                yield Footer()

        async def type_text(pilot):
            input_field = pilot.app.query_one(InputField)
            input_field.input_widget.value = "Hello, OpenHands!"
            await pilot.pause()

        assert snap_compare(
            InputFieldWithTextApp(),
            terminal_size=(80, 24),
            run_before=type_text,
        )


class TestOpenHandsAppSnapshots:
    """Snapshot tests for the main OpenHandsApp.

    Note: These tests mock certain components to avoid external dependencies
    like API calls and file system operations during snapshot testing.
    """

    @pytest.fixture
    def mock_splash_content(self):
        """Mock splash content to ensure consistent snapshots."""
        return {
            "banner": "[bold cyan]OpenHands[/bold cyan]",
            "version": "OpenHands CLI v1.0.0-test",
            "status_text": "All set up!",
            "conversation_text": "Initialized conversation [bold]test-123[/bold]",
            "conversation_id": "test-123",
            "instructions_header": "[bold]What do you want to build?[/bold]",
            "instructions": [
                "1. Ask questions, edit files, or run commands.",
                "2. Use @ to look up a file in the folder structure.",
                "3. Type /help for available commands.",
            ],
            "update_notice": None,
        }

    def test_openhands_app_splash_screen(
        self, snap_compare, mock_splash_content, setup_test_agent_config
    ):
        """Snapshot test for OpenHandsApp splash screen.

        This test uses mocks to avoid external dependencies.
        """

        # Mock the splash content and WORK_DIR to be deterministic
        with (
            patch(
                "openhands_cli.tui.textual_app.get_splash_content",
                return_value=mock_splash_content,
            ),
            patch(
                "openhands_cli.tui.modals.settings.settings_screen.SettingsScreen.is_initial_setup_required",
                return_value=False,
            ),
            patch(
                "openhands_cli.tui.widgets.status_line.WORK_DIR",
                "/test/workspace",
            ),
        ):
            from openhands_cli.tui.textual_app import OpenHandsApp

            app = OpenHandsApp(exit_confirmation=False)
            assert snap_compare(app, terminal_size=(120, 40))


class TestConfirmationModalSnapshots:
    """Snapshot tests for the confirmation settings modal."""

    def test_confirmation_settings_modal(self, snap_compare):
        """Snapshot test for the confirmation settings modal."""
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm
        from openhands_cli.tui.modals.confirmation_modal import (
            ConfirmationSettingsModal,
        )

        class ConfirmationModalTestApp(App):
            CSS = """
            Screen {
                align: center middle;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Background content")
                yield Footer()

            def on_mount(self) -> None:
                modal = ConfirmationSettingsModal(
                    current_policy=AlwaysConfirm(),
                    on_policy_selected=lambda p: None,
                )
                self.push_screen(modal)

        assert snap_compare(ConfirmationModalTestApp(), terminal_size=(100, 30))


# Additional utility for debugging
def run_snapshot_debug():
    """Run the app interactively for debugging purposes.

    This is not a test - it's a utility function that can be called
    to visually inspect the app:

        python -c "from tests.snapshots.test_app_snapshots import ..."
    """
    from openhands_cli.tui.textual_app import OpenHandsApp

    app = OpenHandsApp(exit_confirmation=True)
    app.run()


if __name__ == "__main__":
    run_snapshot_debug()
