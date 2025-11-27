"""
Textual-compatible visualizer for OpenHands conversation events.
This replaces the Rich-based CLIVisualizer with a Textual-compatible version.
"""

import re
import threading
from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.text import Text

from openhands.sdk.conversation.visualizer.base import ConversationVisualizerBase
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
    UserRejectObservation,
)
from openhands.sdk.event.base import Event
from openhands.sdk.event.condenser import Condensation


if TYPE_CHECKING:
    from textual.widgets import RichLog

    from openhands_cli.refactor.textual_app import OpenHandsApp


# Color scheme matching the original visualizer
_OBSERVATION_COLOR = "yellow"
_MESSAGE_USER_COLOR = "gold3"
_PAUSE_COLOR = "bright_yellow"
_SYSTEM_COLOR = "magenta"
_THOUGHT_COLOR = "bright_black"
_ERROR_COLOR = "red"
_ACTION_COLOR = "blue"
_MESSAGE_ASSISTANT_COLOR = _ACTION_COLOR

DEFAULT_HIGHLIGHT_REGEX = {
    r"^Reasoning:": f"bold {_THOUGHT_COLOR}",
    r"^Thought:": f"bold {_THOUGHT_COLOR}",
    r"^Action:": f"bold {_ACTION_COLOR}",
    r"^Arguments:": f"bold {_ACTION_COLOR}",
    r"^Tool:": f"bold {_OBSERVATION_COLOR}",
    r"^Result:": f"bold {_OBSERVATION_COLOR}",
    r"^Rejection Reason:": f"bold {_ERROR_COLOR}",
    # Markdown-style
    r"\*\*(.*?)\*\*": "bold",
    r"\*(.*?)\*": "italic",
}

_PANEL_PADDING = (1, 1)


class TextualVisualizer(ConversationVisualizerBase):
    """Handles visualization of conversation events for Textual apps.

    This visualizer outputs to a Textual RichLog widget instead of directly to console.
    """

    def __init__(
        self,
        rich_log: "RichLog",
        app: "OpenHandsApp",
        highlight_regex: dict[str, str] | None = DEFAULT_HIGHLIGHT_REGEX,
        skip_user_messages: bool = False,
    ):
        """Initialize the visualizer.

        Args:
            rich_log: The Textual RichLog widget to write to
            app: The Textual app instance for thread-safe UI updates
            name: Optional name to prefix in panel titles
            highlight_regex: Dictionary mapping regex patterns to Rich color styles
            skip_user_messages: If True, skip displaying user messages
        """
        super().__init__()
        self._rich_log = rich_log
        self._app = app
        self._skip_user_messages = skip_user_messages
        self._highlight_patterns = highlight_regex or {}
        # Store the main thread ID for thread safety checks
        self._main_thread_id = threading.get_ident()

    def on_event(self, event: Event) -> None:
        """Main event handler that displays events with Rich formatting."""
        panel = self._create_event_panel(event)
        if panel:
            # Check if we're in the main thread or a background thread
            current_thread_id = threading.get_ident()
            if current_thread_id == self._main_thread_id:
                # We're in the main thread, update UI directly
                self._write_panel_to_ui(panel)
            else:
                # We're in a background thread, use call_from_thread
                self._app.call_from_thread(self._write_panel_to_ui, panel)

    def _write_panel_to_ui(self, panel: Panel) -> None:
        """Write a panel to the UI (must be called from main thread)."""
        self._rich_log.write(panel)
        self._rich_log.write("")  # Add spacing between events

    def _apply_highlighting(self, text: Text) -> Text:
        """Apply regex-based highlighting to text content."""
        if not self._highlight_patterns:
            return text

        # Create a copy to avoid modifying the original
        highlighted = text.copy()

        # Apply each pattern using Rich's built-in highlight_regex method
        for pattern, style in self._highlight_patterns.items():
            pattern_compiled = re.compile(pattern, re.MULTILINE)
            highlighted.highlight_regex(pattern_compiled, style)

        return highlighted

    def _create_event_panel(self, event: Event) -> Panel | None:
        """Create a Rich Panel for the event with appropriate styling."""
        # Use the event's visualize property for content
        content = event.visualize

        if not content.plain.strip():
            return None

        # Apply highlighting if configured
        if self._highlight_patterns:
            content = self._apply_highlighting(content)

        # Don't emit system prompt in CLI
        if isinstance(event, SystemPromptEvent):
            return None
        elif isinstance(event, ActionEvent):
            # Check if action is None (non-executable)
            title = f"[bold {_ACTION_COLOR}]"
            if event.action is None:
                title += f"Agent Action (Not Executed)[/bold {_ACTION_COLOR}]"
            else:
                title += f"Agent Action[/bold {_ACTION_COLOR}]"
            return Panel(
                content,
                title=title,
                subtitle=self._format_metrics_subtitle(),
                border_style=_ACTION_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, ObservationEvent):
            title = f"[bold {_OBSERVATION_COLOR}]"
            title += f"Observation[/bold {_OBSERVATION_COLOR}]"
            return Panel(
                content,
                title=title,
                border_style=_OBSERVATION_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, UserRejectObservation):
            title = f"[bold {_ERROR_COLOR}]"
            title += f"User Rejected Action[/bold {_ERROR_COLOR}]"
            return Panel(
                content,
                title=title,
                border_style=_ERROR_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, MessageEvent):
            if (
                self._skip_user_messages
                and event.llm_message
                and event.llm_message.role == "user"
            ):
                return None
            assert event.llm_message is not None
            # Role-based styling
            role_colors = {
                "user": _MESSAGE_USER_COLOR,
                "assistant": _MESSAGE_ASSISTANT_COLOR,
            }
            role_color = role_colors.get(event.llm_message.role, "white")
            if event.llm_message.role == "user":
                title_text = (
                    f"[bold {role_color}]User Message to Agent[/bold {role_color}]"
                )
            else:
                title_text = (
                    f"[bold {role_color}]Message from Agent[/bold {role_color}]"
                )
            return Panel(
                content,
                title=title_text,
                subtitle=self._format_metrics_subtitle(),
                border_style=role_color,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, AgentErrorEvent):
            title = f"[bold {_ERROR_COLOR}]"
            title += f"Agent Error[/bold {_ERROR_COLOR}]"
            return Panel(
                content,
                title=title,
                subtitle=self._format_metrics_subtitle(),
                border_style=_ERROR_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, PauseEvent):
            title = f"[bold {_PAUSE_COLOR}]"
            title += f"User Paused[/bold {_PAUSE_COLOR}]"
            return Panel(
                content,
                title=title,
                border_style=_PAUSE_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )
        elif isinstance(event, Condensation):
            title = f"[bold {_SYSTEM_COLOR}]"
            title += f"Condensation[/bold {_SYSTEM_COLOR}]"
            return Panel(
                content,
                title=title,
                subtitle=self._format_metrics_subtitle(),
                border_style=_SYSTEM_COLOR,
                expand=True,
            )
        else:
            # Fallback panel for unknown event types
            title = f"[bold {_ERROR_COLOR}]"
            title += f"UNKNOWN Event: {event.__class__.__name__}[/bold {_ERROR_COLOR}]"
            return Panel(
                content,
                title=title,
                subtitle=f"({event.source})",
                border_style=_ERROR_COLOR,
                padding=_PANEL_PADDING,
                expand=True,
            )

    def _format_metrics_subtitle(self) -> str | None:
        """Format LLM metrics as a visually appealing subtitle string."""
        stats = self.conversation_stats
        if not stats:
            return None

        combined_metrics = stats.get_combined_metrics()
        if not combined_metrics or not combined_metrics.accumulated_token_usage:
            return None

        usage = combined_metrics.accumulated_token_usage
        cost = combined_metrics.accumulated_cost or 0.0

        # helper: 1234 -> "1.2K", 1200000 -> "1.2M"
        def abbr(n: int | float) -> str:
            n = int(n or 0)
            if n >= 1_000_000_000:
                val, suffix = n / 1_000_000_000, "B"
            elif n >= 1_000_000:
                val, suffix = n / 1_000_000, "M"
            elif n >= 1_000:
                val, suffix = n / 1_000, "K"
            else:
                return str(n)
            return f"{val:.2f}".rstrip("0").rstrip(".") + suffix

        input_tokens = abbr(usage.prompt_tokens or 0)
        output_tokens = abbr(usage.completion_tokens or 0)

        # Cache hit rate (prompt + cache)
        prompt = usage.prompt_tokens or 0
        cache_read = usage.cache_read_tokens or 0
        cache_rate = f"{(cache_read / prompt * 100):.2f}%" if prompt > 0 else "N/A"
        reasoning_tokens = usage.reasoning_tokens or 0

        # Cost
        cost_str = f"{cost:.4f}" if cost > 0 else "0.00"

        # Build with fixed color scheme
        parts: list[str] = []
        parts.append(f"[cyan]↑ input {input_tokens}[/cyan]")
        parts.append(f"[magenta]cache hit {cache_rate}[/magenta]")
        if reasoning_tokens > 0:
            parts.append(f"[yellow] reasoning {abbr(reasoning_tokens)}[/yellow]")
        parts.append(f"[blue]↓ output {output_tokens}[/blue]")
        parts.append(f"[green]$ {cost_str}[/green]")

        return "Tokens: " + " • ".join(parts)
