"""Snapshot tests for the status line alignment.

These tests verify that the status line text is properly aligned with
the input box content (accounting for the input box border).
"""

import types

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.signal import Signal
from textual.widgets import Input

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.widgets.status_line import InfoStatusLine, WorkingStatusLine


class StatusLineTestApp(App):
    """Test app for status line alignment snapshots.

    Uses the same CSS structure as the real OpenHands CLI app's input_area
    to ensure accurate visual testing of alignment.
    """

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
    }
    /* Matches #input_area from textual_app.tcss */
    #input_area {
        height: auto;
        dock: bottom;
        background: $background;
        padding: 1;
    }
    /* Matches #user_input from input_field.py */
    #test_input {
        width: 100%;
        height: 3;
        background: $background;
        color: $foreground;
        border: solid $secondary;
    }
    /* Status line alignment - matches input content position */
    #working_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1 0 3;
    }
    #info_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1 0 3;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.register_theme(OPENHANDS_THEME)
        self.theme = "openhands"
        # Create mock signals for the status lines
        self.conversation_running_signal = Signal(self, "conversation_running")
        # Create mock input_field with multiline mode signal
        self.input_field = types.SimpleNamespace(
            mutliline_mode_status=Signal(self, "multiline_mode")
        )
        self.conversation_runner = None

    def compose(self) -> ComposeResult:
        with Vertical(id="input_area"):
            yield WorkingStatusLine(app=self)
            yield Input(placeholder="Type your message...", id="test_input")
            yield InfoStatusLine(app=self)


class TestStatusLineSnapshots:
    """Snapshot tests for status line alignment."""

    def test_status_line_alignment_with_input(self, snap_compare):
        """Verify status line text aligns with input box content.

        The input box has a border which adds visual offset. The status line
        should have matching left padding so text aligns properly.
        """
        assert snap_compare(StatusLineTestApp(), terminal_size=(100, 10))

    def test_status_line_alignment_narrow_terminal(self, snap_compare):
        """Verify status line alignment in narrow terminal."""
        assert snap_compare(StatusLineTestApp(), terminal_size=(60, 10))
