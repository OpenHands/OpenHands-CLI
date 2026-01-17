from __future__ import annotations

import os

from textual import on
from textual.timer import Timer
from textual.widgets import Static

from openhands_cli.locations import WORK_DIR
from openhands_cli.tui.core.state import StateChanged, ConversationStarted, ConversationFinished
from openhands_cli.utils import abbreviate_number, format_cost


class WorkingStatusLine(Static):
    """Status line showing conversation timer and working indicator (above input).
    
    This widget listens for state change messages from StateManager.
    """

    DEFAULT_CSS = """
    #working_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", id="working_status_line", markup=False, **kwargs)
        self._timer: Timer | None = None
        self._working_frame: int = 0
        self._is_running: bool = False
        self._elapsed_seconds: int = 0

    def on_mount(self) -> None:
        """Initialize the working status line and start animation timer."""
        self._update_text()
        # Start animation timer for spinner (runs continuously but only animates when working)
        self._timer = self.set_interval(0.1, self._on_tick)

    def on_unmount(self) -> None:
        """Stop timer when widget is removed."""
        if self._timer:
            self._timer.stop()
            self._timer = None

    # ----- Message Handlers -----
    
    @on(ConversationStarted)
    def _on_conversation_started(self, event: ConversationStarted) -> None:
        """Handle conversation start."""
        self._is_running = True
        self._elapsed_seconds = 0
        self._update_text()
    
    @on(ConversationFinished)
    def _on_conversation_finished(self, event: ConversationFinished) -> None:
        """Handle conversation end."""
        self._is_running = False
        self._update_text()
    
    @on(StateChanged)
    def _on_state_changed(self, event: StateChanged) -> None:
        """Handle state changes from StateManager."""
        if event.key == "elapsed_seconds":
            self._elapsed_seconds = event.new_value
            self._update_text()

    # ----- Internal helpers -----

    def _on_tick(self) -> None:
        """Periodic update for animation."""
        if self._is_running:
            self._working_frame = (self._working_frame + 1) % 8
            self._update_text()

    def _get_working_text(self) -> str:
        """Return working status text if conversation is running."""
        if not self._is_running:
            return ""

        # Add working indicator with Braille spinner animation
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]
        working_indicator = f"{frames[self._working_frame % len(frames)]} Working"

        return f"{working_indicator} ({self._elapsed_seconds}s • ESC: pause)"

    def _update_text(self) -> None:
        """Rebuild the working status text."""
        working_text = self._get_working_text()
        self.update(working_text if working_text else " ")


class InfoStatusLine(Static):
    """Status line showing work directory, input mode, and conversation metrics.
    
    This widget listens for state change messages from StateManager.
    """

    DEFAULT_CSS = """
    #info_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", id="info_status_line", markup=True, **kwargs)
        self.work_dir_display = self._get_work_dir_display()
        # Internal state
        self._is_multiline_mode: bool = False
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._cache_hit_rate: str = "N/A"
        self._last_request_input_tokens: int = 0
        self._context_window: int = 0
        self._accumulated_cost: float = 0.0

    def on_mount(self) -> None:
        """Initialize the info status line."""
        self._update_text()

    def on_resize(self) -> None:
        """Recalculate layout when widget is resized."""
        self._update_text()

    # ----- Message Handlers -----
    
    @on(StateChanged)
    def _on_state_changed(self, event: StateChanged) -> None:
        """Handle state changes from StateManager."""
        key = event.key
        value = event.new_value
        
        if key == "is_multiline_mode":
            self._is_multiline_mode = value
        elif key == "input_tokens":
            self._input_tokens = value
        elif key == "output_tokens":
            self._output_tokens = value
        elif key == "cache_hit_rate":
            self._cache_hit_rate = value
        elif key == "last_request_input_tokens":
            self._last_request_input_tokens = value
        elif key == "context_window":
            self._context_window = value
        elif key == "accumulated_cost":
            self._accumulated_cost = value
        else:
            return  # Don't update for unrelated state changes
        
        self._update_text()

    # ----- Internal helpers -----

    @property
    def mode_indicator(self) -> str:
        """Get the mode indicator text based on current mode."""
        if self._is_multiline_mode:
            return "\\[Multi-line: Ctrl+J to submit • Ctrl+X for custom editor]"
        return "\\[Ctrl+L for multi-line • Ctrl+X for custom editor]"

    def _get_work_dir_display(self) -> str:
        """Get the work directory display string with tilde-shortening."""
        work_dir = WORK_DIR
        home = os.path.expanduser("~")
        if work_dir.startswith(home):
            work_dir = work_dir.replace(home, "~", 1)
        return work_dir

    def _format_metrics_display(self) -> str:
        """Format the conversation metrics for display.

        Shows: context (current / total) • cost (input tokens • output tokens • cache)
        """
        # Context display: show current context usage / total context window
        if self._last_request_input_tokens > 0:
            ctx_current = abbreviate_number(self._last_request_input_tokens)
            if self._context_window > 0:
                ctx_total = abbreviate_number(self._context_window)
                ctx_display = f"ctx {ctx_current} / {ctx_total}"
            else:
                ctx_display = f"ctx {ctx_current}"
        else:
            ctx_display = "ctx N/A"

        cost_display = f"$ {format_cost(self._accumulated_cost)}"
        token_details = (
            f"↑ {abbreviate_number(self._input_tokens)} "
            f"↓ {abbreviate_number(self._output_tokens)} "
            f"cache {self._cache_hit_rate}"
        )
        return f"{ctx_display} • {cost_display} ({token_details})"

    def _update_text(self) -> None:
        """Rebuild the info status text with metrics right-aligned in grey."""
        left_part = f"{self.mode_indicator} • {self.work_dir_display}"
        metrics_display = self._format_metrics_display()

        # Calculate available width for spacing (account for padding of 2 chars)
        try:
            total_width = self.size.width - 2
        except Exception:
            total_width = 80  # Fallback width

        # Calculate spacing needed to right-align metrics
        left_len = len(left_part)
        right_len = len(metrics_display)
        spacing = max(1, total_width - left_len - right_len)

        # Build status text with grey metrics on the right
        status_text = f"{left_part}{' ' * spacing}[grey50]{metrics_display}[/grey50]"
        self.update(status_text)
