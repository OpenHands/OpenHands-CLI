from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from textual.timer import Timer
from textual.widgets import Static

from openhands_cli.locations import get_work_dir
from openhands_cli.utils import abbreviate_number, format_cost


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


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
    """Status line showing work directory, input mode, and conversation metrics."""

    DEFAULT_CSS = """
    #info_status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, app: OpenHandsApp, **kwargs) -> None:
        super().__init__("", id="info_status_line", markup=True, **kwargs)
        self.main_app = app
        self.mode_indicator = "\\[Ctrl+L for multi-line • Ctrl+X for custom editor]"
        self.work_dir_display = self._get_work_dir_display()
        # Conversation metrics
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._cache_hit_rate: str = "N/A"
        self._last_request_input_tokens: int = 0  # Current context usage
        self._context_window: int = 0  # Total context window
        self._accumulated_cost: float = 0.0
        self._metrics_update_timer: Timer | None = None

    def on_mount(self) -> None:
        """Initialize the info status line."""
        self._update_text()
        self.main_app.input_field.multiline_mode_status.subscribe(
            self, self._on_handle_mutliline_mode
        )
        self.main_app.conversation_running_signal.subscribe(
            self, self._on_conversation_state_changed
        )

    def reset_metrics(self) -> None:
        """Reset all conversation metrics to initial state."""
        self._input_tokens = 0
        self._output_tokens = 0
        self._cache_hit_rate = "N/A"
        self._last_request_input_tokens = 0
        self._context_window = 0
        self._accumulated_cost = 0.0
        self._update_text()

    def on_unmount(self) -> None:
        """Stop timer when widget is removed."""
        if self._metrics_update_timer:
            self._metrics_update_timer.stop()
            self._metrics_update_timer = None

    def on_resize(self) -> None:
        """Recalculate layout when widget is resized."""
        self._update_text()

    def _on_conversation_state_changed(self, is_running: bool) -> None:
        """Update metrics display when conversation state changes."""
        if is_running:
            # Start periodic metrics updates while conversation is running
            if self._metrics_update_timer:
                self._metrics_update_timer.stop()
            self._metrics_update_timer = self.set_interval(1.0, self._update_metrics)
        else:
            # Stop timer and do final metrics update
            if self._metrics_update_timer:
                self._metrics_update_timer.stop()
                self._metrics_update_timer = None
            self._update_metrics()

    def _update_metrics(self) -> None:
        """Update the conversation metrics from conversation stats."""
        if self.main_app.conversation_runner:
            visualizer = self.main_app.conversation_runner.visualizer
            stats = visualizer.conversation_stats
            if stats:
                combined_metrics = stats.get_combined_metrics()
                if combined_metrics:
                    self._accumulated_cost = combined_metrics.accumulated_cost or 0.0
                    usage = combined_metrics.accumulated_token_usage
                    if usage:
                        self._input_tokens = usage.prompt_tokens or 0
                        self._output_tokens = usage.completion_tokens or 0
                        self._context_window = usage.context_window or 0
                        # Calculate cache hit rate
                        prompt = usage.prompt_tokens or 0
                        cache_read = usage.cache_read_tokens or 0
                        if prompt > 0:
                            self._cache_hit_rate = f"{(cache_read / prompt * 100):.0f}%"
                        else:
                            self._cache_hit_rate = "N/A"
                    # Get last request's input tokens (current context usage)
                    token_usages = combined_metrics.token_usages
                    if token_usages:
                        self._last_request_input_tokens = (
                            token_usages[-1].prompt_tokens or 0
                        )
                    else:
                        self._last_request_input_tokens = 0
        self._update_text()

    def _on_handle_mutliline_mode(self, is_multiline_mode: bool) -> None:
        if is_multiline_mode:
            self.mode_indicator = (
                "\\[Multi-line: Ctrl+J to submit • Ctrl+X for custom editor]"
            )
        else:
            self.mode_indicator = "\\[Ctrl+L for multi-line • Ctrl+X for custom editor]"
        self._update_text()

    def _get_work_dir_display(self) -> str:
        """Get the work directory display string with tilde-shortening."""
        work_dir = get_work_dir()
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
