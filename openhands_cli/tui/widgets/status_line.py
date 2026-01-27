from __future__ import annotations

import os

from textual.reactive import var
from textual.timer import Timer
from textual.widgets import Static

from openhands.sdk.llm.utils.metrics import Metrics
from openhands_cli.locations import WORK_DIR
from openhands_cli.utils import abbreviate_number, format_cost


class WorkingStatusLine(Static):
    """Status line showing conversation timer and working indicator (above input).

    This widget uses data_bind() to bind to StateManager reactive properties.
    When StateManager.is_running or StateManager.elapsed_seconds change,
    this widget's corresponding properties are automatically updated.
    """

    DEFAULT_CSS = """
    #working_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
    }
    """

    running: var[bool] = var(False)
    elapsed_seconds: var[int] = var(0)

    def __init__(self, **kwargs) -> None:
        super().__init__("", id="working_status_line", markup=False, **kwargs)
        self._timer: Timer | None = None
        self._working_frame: int = 0

    def on_mount(self) -> None:
        """Initialize the working status line and start animation timer."""
        self._update_text()
        # Start animation timer for spinner (animates only when working)
        self._timer = self.set_interval(0.1, self._on_tick)

    def on_unmount(self) -> None:
        """Stop timer when widget is removed."""
        if self._timer:
            self._timer.stop()
            self._timer = None

    # ----- Reactive Watchers -----

    def watch_running(self, _running: bool) -> None:
        """React to running state changes from StateManager."""
        self._update_text()

    # ----- Internal helpers -----

    def _on_tick(self) -> None:
        """Periodic update for animation."""
        if self.running:
            self._working_frame = (self._working_frame + 1) % 8
            self._update_text()

    def _get_working_text(self) -> str:
        """Return working status text if conversation is running."""
        if not self.running:
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

    This widget uses data_bind() to bind to StateManager reactive properties.
    When StateManager metrics change, this widget automatically updates.
    """

    DEFAULT_CSS = """
    #info_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
    }
    """

    # Reactive properties bound via data_bind() to StateManager
    # Note: Named 'running' to avoid conflict with MessagePump.is_running
    running: var[bool] = var(False)
    is_multiline_mode: var[bool] = var(False)
    # Metrics object from conversation stats (bound from StateManager)
    metrics: var[Metrics | None] = var(None)

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

    def watch_is_multiline_mode(self, _value: bool) -> None:
        """React to multiline mode changes from StateManager."""
        self._update_text()

    def watch_metrics(self, _value: Metrics | None) -> None:
        """React to metrics changes from StateManager."""
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
        # Extract values from metrics object
        if self.metrics is None:
            return "ctx N/A • $ 0.00 (↑ 0 ↓ 0 cache N/A)"

        usage = self.metrics.accumulated_token_usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        context_window = usage.context_window if usage else 0
        cache_read_tokens = usage.cache_read_tokens if usage else 0
        accumulated_cost = self.metrics.accumulated_cost or 0.0

        # Get last request input tokens from token_usages list
        last_request_input_tokens = 0
        if self.metrics.token_usages:
            last_request_input_tokens = self.metrics.token_usages[-1].prompt_tokens or 0

        # Calculate cache hit rate
        if input_tokens > 0:
            cache_hit_rate = f"{(cache_read_tokens / input_tokens * 100):.0f}%"
        else:
            cache_hit_rate = "N/A"

        # Context display: show current context usage / total context window
        if last_request_input_tokens > 0:
            ctx_current = abbreviate_number(last_request_input_tokens)
            if context_window > 0:
                ctx_total = abbreviate_number(context_window)
                ctx_display = f"ctx {ctx_current} / {ctx_total}"
            else:
                ctx_display = f"ctx {ctx_current}"
        else:
            ctx_display = "ctx N/A"

        cost_display = f"$ {format_cost(accumulated_cost)}"
        token_details = (
            f"↑ {abbreviate_number(input_tokens)} "
            f"↓ {abbreviate_number(output_tokens)} "
            f"cache {cache_hit_rate}"
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
