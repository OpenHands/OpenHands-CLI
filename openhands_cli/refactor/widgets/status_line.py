from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from textual.timer import Timer
from textual.widgets import Static

from openhands_cli.locations import WORK_DIR


if TYPE_CHECKING:
    from openhands_cli.refactor.textual_app import OpenHandsApp


class WorkingStatusLine(Static):
    """Status line showing conversation timer and working indicator (above input)."""

    DEFAULT_CSS = """
    #working_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, app: OpenHandsApp, **kwargs) -> None:
        super().__init__("", id="working_status_line", markup=False, **kwargs)
        self._conversation_start_time: float | None = None
        self._timer: Timer | None = None
        self._working_frame: int = 0
        self._is_working: bool = False

        self.main_app = app

    def on_mount(self) -> None:
        """Initialize the working status line and start periodic updates."""
        self._update_text()
        self.main_app.conversation_running_signal.subscribe(
            self, self._on_conversation_state_changed
        )

    def on_unmount(self) -> None:
        """Stop timer when widget is removed."""
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _on_conversation_state_changed(self, is_running: bool) -> None:
        """Update when conversation running state changes."""
        self._is_working = is_running
        if is_running:
            self._conversation_start_time = time.time()
            if self._timer:
                self._timer.stop()

            self._timer = self.set_interval(0.1, self._on_tick)
            return

        self._conversation_start_time = None
        if self._timer:
            self._timer.stop()
            self._timer = None

        self._update_text()

    # ----- Internal helpers -----

    def _on_tick(self) -> None:
        """Periodic update from timer."""
        if self._conversation_start_time is not None:
            # Update animation frame more frequently than timer for smooth animation
            if self._is_working:
                self._working_frame = (self._working_frame + 1) % 8
            self._update_text()

    def _get_working_text(self) -> str:
        """Return working status text if conversation is running."""
        if not self._conversation_start_time:
            return ""
        elapsed = int(time.time() - self._conversation_start_time)

        # Add working indicator with Braille spinner animation
        working_indicator = ""
        if self._is_working:
            # Braille pattern spinner - smooth and professional
            frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]
            working_indicator = f"{frames[self._working_frame % len(frames)]} Working"

        return f"{working_indicator} ({elapsed}s • ESC: pause)"

    def _update_text(self) -> None:
        """Rebuild the working status text."""
        working_text = self._get_working_text()
        self.update(working_text if working_text else " ")


class InfoStatusLine(Static):
    """Status line showing work directory and input mode (below input)."""

    DEFAULT_CSS = """
    #info_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, app: OpenHandsApp, **kwargs) -> None:
        super().__init__("", id="info_status_line", markup=False, **kwargs)
        self.main_app = app
        self.mode_indicator = "[Ctrl+L for multi-line]"
        self.work_dir_display = self._get_work_dir_display()

    def on_mount(self) -> None:
        """Initialize the info status line."""
        self._update_text()
        self.main_app.input_field.mutliline_mode_status.subscribe(
            self, self._on_handle_mutliline_mode
        )

    def _on_handle_mutliline_mode(self, is_multiline_mode: bool) -> None:
        if is_multiline_mode:
            self.mode_indicator = "[Multi-line: Ctrl+J to submit]"
        else:
            self.mode_indicator = "[Ctrl+L for multi-line]"
        self._update_text()

    def _get_work_dir_display(self) -> str:
        """Get the work directory display string with tilde-shortening."""
        work_dir = WORK_DIR
        home = os.path.expanduser("~")
        if work_dir.startswith(home):
            work_dir = work_dir.replace(home, "~", 1)
        return work_dir

    def _update_text(self) -> None:
        """Rebuild the info status text."""
        status_text = f"{self.mode_indicator} • {self.work_dir_display}"
        self.update(status_text)
