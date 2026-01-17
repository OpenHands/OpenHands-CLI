from __future__ import annotations

import os

from textual.reactive import var
from textual.timer import Timer
from textual.widgets import Static

from openhands_cli.locations import WORK_DIR
from openhands_cli.utils import abbreviate_number, format_cost


class WorkingStatusLine(Static):
    """Status line showing conversation timer and working indicator (above input).
    
    This widget uses Textual's reactive system for state management.
    Bind to StateManager properties using data_bind() for automatic updates:
    
        status_line.data_bind(
            is_running=StateManager.is_running,
            elapsed_seconds=StateManager.elapsed_seconds
        )
    """

    DEFAULT_CSS = """
    #working_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
    }
    """
    
    # Reactive properties bound to StateManager
    is_running: var[bool] = var(False)
    elapsed_seconds: var[int] = var(0)

    def __init__(self, **kwargs) -> None:
        super().__init__("", id="working_status_line", markup=False, **kwargs)
        self._timer: Timer | None = None
        self._working_frame: int = 0

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

    # ----- Reactive Watchers -----
    
    def watch_is_running(self, is_running: bool) -> None:
        """React to running state changes."""
        self._update_text()
    
    def watch_elapsed_seconds(self, elapsed: int) -> None:
        """React to elapsed time changes."""
        self._update_text()

    # ----- Internal helpers -----

    def _on_tick(self) -> None:
        """Periodic update for animation."""
        if self.is_running:
            self._working_frame = (self._working_frame + 1) % 8
            self._update_text()

    def _get_working_text(self) -> str:
        """Return working status text if conversation is running."""
        if not self.is_running:
            return ""

        # Add working indicator with Braille spinner animation
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]
        working_indicator = f"{frames[self._working_frame % len(frames)]} Working"

        return f"{working_indicator} ({self.elapsed_seconds}s • ESC: pause)"

    def _update_text(self) -> None:
        """Rebuild the working status text."""
        working_text = self._get_working_text()
        self.update(working_text if working_text else " ")


class InfoStatusLine(Static):
    """Status line showing work directory, input mode, and conversation metrics.
    
    This widget uses Textual's reactive system for state management.
    Bind to StateManager properties using data_bind() for automatic updates:
    
        info_line.data_bind(
            is_running=StateManager.is_running,
            is_multiline_mode=StateManager.is_multiline_mode,
            input_tokens=StateManager.input_tokens,
            ...
        )
    """

    DEFAULT_CSS = """
    #info_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
    }
    """
    
    # Reactive properties bound to StateManager
    is_running: var[bool] = var(False)
    is_multiline_mode: var[bool] = var(False)
    input_tokens: var[int] = var(0)
    output_tokens: var[int] = var(0)
    cache_hit_rate: var[str] = var("N/A")
    last_request_input_tokens: var[int] = var(0)
    context_window: var[int] = var(0)
    accumulated_cost: var[float] = var(0.0)

    def __init__(self, **kwargs) -> None:
        super().__init__("", id="info_status_line", markup=True, **kwargs)
        self.work_dir_display = self._get_work_dir_display()

    def on_mount(self) -> None:
        """Initialize the info status line."""
        self._update_text()

    def on_resize(self) -> None:
        """Recalculate layout when widget is resized."""
        self._update_text()

    # ----- Reactive Watchers -----
    
    def watch_is_multiline_mode(self, is_multiline: bool) -> None:
        """React to multiline mode changes."""
        self._update_text()
    
    def watch_input_tokens(self, value: int) -> None:
        """React to input token changes."""
        self._update_text()
    
    def watch_output_tokens(self, value: int) -> None:
        """React to output token changes."""
        self._update_text()
    
    def watch_accumulated_cost(self, value: float) -> None:
        """React to cost changes."""
        self._update_text()
    
    def watch_cache_hit_rate(self, value: str) -> None:
        """React to cache hit rate changes."""
        self._update_text()
    
    def watch_last_request_input_tokens(self, value: int) -> None:
        """React to context usage changes."""
        self._update_text()
    
    def watch_context_window(self, value: int) -> None:
        """React to context window changes."""
        self._update_text()

    # ----- Internal helpers -----

    @property
    def mode_indicator(self) -> str:
        """Get the mode indicator text based on current mode."""
        if self.is_multiline_mode:
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
        if self.last_request_input_tokens > 0:
            ctx_current = abbreviate_number(self.last_request_input_tokens)
            if self.context_window > 0:
                ctx_total = abbreviate_number(self.context_window)
                ctx_display = f"ctx {ctx_current} / {ctx_total}"
            else:
                ctx_display = f"ctx {ctx_current}"
        else:
            ctx_display = "ctx N/A"

        cost_display = f"$ {format_cost(self.accumulated_cost)}"
        token_details = (
            f"↑ {abbreviate_number(self.input_tokens)} "
            f"↓ {abbreviate_number(self.output_tokens)} "
            f"cache {self.cache_hit_rate}"
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
