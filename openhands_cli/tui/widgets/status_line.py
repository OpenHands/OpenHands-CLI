from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING

from textual.timer import Timer
from textual.widgets import Static

from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.cloud.conversation import is_token_valid
from openhands_cli.constants import WORK_DIR
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
        # Cloud connection status
        self._cloud_connected: bool | None = None  # None = unknown/checking
        self._cloud_check_task: asyncio.Task | None = None

    def on_mount(self) -> None:
        """Initialize the info status line."""
        self._update_text()
        self.main_app.input_field.multiline_mode_status.subscribe(
            self, self._on_handle_mutliline_mode
        )
        self.main_app.conversation_running_signal.subscribe(
            self, self._on_conversation_state_changed
        )
        # Start async check for cloud connection
        self._cloud_check_task = asyncio.create_task(self._check_cloud_connection())

    def on_unmount(self) -> None:
        """Stop timer when widget is removed."""
        if self._metrics_update_timer:
            self._metrics_update_timer.stop()
            self._metrics_update_timer = None
        if self._cloud_check_task and not self._cloud_check_task.done():
            self._cloud_check_task.cancel()

    def on_resize(self) -> None:
        """Recalculate layout when widget is resized."""
        self._update_text()

    async def _check_cloud_connection(self) -> None:
        """Check if the cloud connection is valid."""
        token_storage = TokenStorage()
        api_key = token_storage.get_api_key()

        if not api_key:
            self._cloud_connected = False
            self._update_text()
            return

        try:
            cloud_url = self.main_app.cloud_url
            self._cloud_connected = await is_token_valid(cloud_url, api_key)
        except Exception:
            # Any error means we can't connect
            self._cloud_connected = False

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

    def _get_cloud_status_display(self) -> tuple[str, int]:
        """Get the cloud connection status indicator with color markup.

        Returns:
            Tuple of (formatted status string, plain text length for spacing calculation)
        """
        if self._cloud_connected is None:
            text = "☁ Cloud"
            return f"[grey50]{text}[/grey50]", len(text)
        elif self._cloud_connected:
            text = "✓ Cloud"
            return f"[#00ff00]{text}[/#00ff00]", len(text)
        else:
            text = "✗ Cloud"
            return f"[#ff6b6b]{text}[/#ff6b6b]", len(text)

    def _update_text(self) -> None:
        """Rebuild the info status text with metrics and cloud status right-aligned."""
        left_part = f"{self.mode_indicator} • {self.work_dir_display}"
        metrics_display = self._format_metrics_display()
        cloud_status, cloud_status_len = self._get_cloud_status_display()

        # Calculate available width for spacing (account for padding of 2 chars)
        try:
            total_width = self.size.width - 2
        except Exception:
            total_width = 80  # Fallback width

        # Right part includes metrics and cloud status indicator
        right_part_plain = f"{metrics_display} "  # Space before cloud indicator
        right_len = len(right_part_plain) + cloud_status_len

        # Calculate spacing needed to right-align
        left_len = len(left_part)
        spacing = max(1, total_width - left_len - right_len)

        # Build status text with grey metrics and colored cloud status on the right
        status_text = (
            f"{left_part}{' ' * spacing}"
            f"[grey50]{metrics_display}[/grey50] {cloud_status}"
        )
        self.update(status_text)

    def on_click(self, event) -> None:
        """Handle click events - open cloud link modal if clicking on cloud indicator."""
        # Check if click is on the right side (cloud indicator area)
        # The cloud indicator is at the far right of the status line
        try:
            total_width = self.size.width - 2
            # Cloud indicator is in the last ~10 characters (for "✓ Cloud" text)
            if event.x >= total_width - 10:
                self._open_cloud_modal()
        except Exception:
            pass

    def _open_cloud_modal(self) -> None:
        """Open the cloud link modal."""
        from openhands_cli.tui.modals.cloud_link_modal import CloudLinkModal

        modal = CloudLinkModal(
            is_connected=self._cloud_connected or False,
            on_link_complete=self._on_cloud_link_complete,
            cloud_url=self.main_app.cloud_url,
        )
        self.main_app.push_screen(modal)

    def _on_cloud_link_complete(self, success: bool) -> None:
        """Handle completion of cloud linking."""
        if success:
            # Re-check connection status
            self._cloud_connected = None
            self._update_text()
            self._cloud_check_task = asyncio.create_task(self._check_cloud_connection())

    @property
    def cloud_connected(self) -> bool | None:
        """Return the current cloud connection status."""
        return self._cloud_connected

    async def refresh_cloud_status(self) -> None:
        """Manually refresh the cloud connection status."""
        self._cloud_connected = None
        self._update_text()
        await self._check_cloud_connection()
