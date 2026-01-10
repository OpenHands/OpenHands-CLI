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

from textual.app import App, ComposeResult
from textual.widgets import Footer, Static

from openhands_cli.tui.modals.exit_modal import ExitConfirmationModal


class TestExitModalSnapshots:
    """Snapshot tests for the ExitConfirmationModal."""

    def test_exit_modal_initial_state(self, snap_compare):
        """Snapshot test for exit confirmation modal initial state."""

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

        assert snap_compare(ExitModalTestApp(), terminal_size=(80, 24))
