from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from textual.timer import Timer
from textual.widgets import Static

from openhands_cli.locations import WORK_DIR


if TYPE_CHECKING:
    from openhands_cli.refactor.textual_app import OpenHandsApp


class StatusLine(Static):
    """Status line showing work dir, input mode, and conversation timer."""

    DEFAULT_CSS = """
    #status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
        margin-bottom: 1;
    }
    """

    def __init__(self, app: OpenHandsApp, **kwargs) -> None:
        super().__init__("", id="status_line", markup=False, **kwargs)
        self._conversation_start_time: float | None = None
        self._timer: Timer | None = None

        self.main_app = app
        self.mode_indicator = " [Ctrl+L for multi-line]"
        self.work_dir_display = self._get_work_dir_display()

    def on_mount(self) -> None:
        """Initialize the status line and start periodic updates."""
        self._update_text()
        self.main_app.input_field.mutliline_mode_status.subscribe(
            self, self._on_handle_mutliline_mode
        )
        self.main_app.conversation_running_signal.subscribe(
            self, self._on_conversation_state_changed
        )

    def on_unmount(self) -> None:
        """Stop timer when widget is removed."""
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _on_handle_mutliline_mode(self, is_multiline_mode: bool) -> None:
        if is_multiline_mode:
            self.mode_indicator = " [Multi-line: Ctrl+J to submit]"
        else:
            self.mode_indicator = " [Ctrl+L for multi-line]"
        self._update_text()

    def _on_conversation_state_changed(self, is_running: bool) -> None:
        """Update when conversation running state changes."""
        if is_running:
            self._conversation_start_time = time.time()
            if self._timer:
                self._timer.stop()

            self._timer = self.set_interval(1.0, self._on_tick)
            return

        self._conversation_start_time = None
        if self._timer:
            self._timer.stop()
            self._timer = None

        self.conversation_start_time = None
        self._update_text()

    # ----- Internal helpers -----

    def _on_tick(self) -> None:
        """Periodic update from timer."""
        if self._conversation_start_time is not None:
            self._update_text()

    def _get_work_dir_display(self) -> str:
        """Get the work directory display string with tilde-shortening."""
        work_dir = WORK_DIR
        home = os.path.expanduser("~")
        if work_dir.startswith(home):
            work_dir = work_dir.replace(home, "~", 1)
        return work_dir

    def _get_elapsed_text(self) -> str:
        """Return timer text if conversation is running."""
        if not self._conversation_start_time:
            return ""
        elapsed = int(time.time() - self._conversation_start_time)
        return f" ✦ (esc to cancel • {elapsed}s , Ctrl+O to show details)"

    def _update_text(self) -> None:
        """Rebuild the full status line text."""
        elapsed = self._get_elapsed_text()

        # When not running, we just omit the elapsed part
        if elapsed:
            status_text = f"{self.work_dir_display}{elapsed}{self.mode_indicator}"
        else:
            status_text = f"{self.work_dir_display}{self.mode_indicator}"

        self.update(status_text)
