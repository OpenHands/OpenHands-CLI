"""
Textual-compatible visualizer for OpenHands conversation events.
This replaces the Rich-based CLIVisualizer with a Textual-compatible version.
"""

import threading
from typing import TYPE_CHECKING

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
from openhands_cli.refactor.core.theme import OPENHANDS_THEME
from openhands_cli.refactor.widgets.non_clickable_collapsible import (
    NonClickableCollapsible,
)


if TYPE_CHECKING:
    from textual.containers import VerticalScroll

    from openhands_cli.refactor.textual_app import OpenHandsApp


def _get_event_border_color(event: Event) -> str:
    DEFAULT_COLOR = "#ffffff"

    """Get the CSS border color for an event type."""
    if isinstance(event, ActionEvent):
        return OPENHANDS_THEME.accent or DEFAULT_COLOR
    elif isinstance(event, ObservationEvent):
        return OPENHANDS_THEME.accent or DEFAULT_COLOR
    elif isinstance(event, UserRejectObservation):
        return OPENHANDS_THEME.error or DEFAULT_COLOR
    elif isinstance(event, MessageEvent):
        if event.llm_message and event.llm_message.role == "user":
            return OPENHANDS_THEME.primary
        else:
            return OPENHANDS_THEME.accent or DEFAULT_COLOR
    elif isinstance(event, AgentErrorEvent):
        return OPENHANDS_THEME.error or DEFAULT_COLOR
    elif isinstance(event, PauseEvent):
        return OPENHANDS_THEME.primary
    elif isinstance(event, Condensation):
        return "#727987"
    else:
        return DEFAULT_COLOR


class TextualVisualizer(ConversationVisualizerBase):
    """Handles visualization of conversation events for Textual apps.

    This visualizer creates Collapsible widgets and adds them to a VerticalScroll
    container.
    """

    def __init__(
        self,
        container: "VerticalScroll",
        app: "OpenHandsApp",
        skip_user_messages: bool = False,
    ):
        """Initialize the visualizer.

        Args:
            container: The Textual VerticalScroll container to add widgets to
            app: The Textual app instance for thread-safe UI updates
            highlight_regex: Dictionary mapping regex patterns to Rich color styles
            skip_user_messages: If True, skip displaying user messages
        """
        super().__init__()
        self._container = container
        self._app = app
        self._skip_user_messages = skip_user_messages
        # Store the main thread ID for thread safety checks
        self._main_thread_id = threading.get_ident()

    def on_event(self, event: Event) -> None:
        """Main event handler that creates Collapsible widgets for events."""
        collapsible_widget = self._create_event_collapsible(event)
        if collapsible_widget:
            # Check if we're in the main thread or a background thread
            current_thread_id = threading.get_ident()
            if current_thread_id == self._main_thread_id:
                # We're in the main thread, update UI directly
                self._add_widget_to_ui(collapsible_widget)
            else:
                # We're in a background thread, use call_from_thread
                self._app.call_from_thread(self._add_widget_to_ui, collapsible_widget)

    def _add_widget_to_ui(self, widget: NonClickableCollapsible) -> None:
        """Add a widget to the UI (must be called from main thread)."""
        self._container.mount(widget)
        # Automatically scroll to the bottom to show the newly added widget
        self._container.scroll_end(animate=False)

    def _escape_rich_markup(self, text: str) -> str:
        """Escape Rich markup characters in text to prevent markup errors."""
        # Escape square brackets which are used for Rich markup
        return text.replace("[", r"\[").replace("]", r"\]")

    def _extract_meaningful_title(self, event, fallback_title: str) -> str:
        """Extract a meaningful title from an event, with fallback to truncated
        content."""
        # Try to extract meaningful information from the event
        if hasattr(event, "action") and event.action is not None:
            # For ActionEvents, try to get action type and details
            action = event.action
            action_type = action.__class__.__name__.replace("Action", "")

            # Try to get specific details based on action type
            if hasattr(action, "command") and action.command:
                # For command actions, show the command
                cmd = str(action.command).strip()
                if len(cmd) > 50:
                    cmd = cmd[:47] + "..."
                return f"{action_type}: {self._escape_rich_markup(cmd)}"
            elif hasattr(action, "path") and action.path:
                # For file actions, show the path
                path = str(action.path)
                if len(path) > 50:
                    path = "..." + path[-47:]  # Show end of path if too long
                return f"{action_type}: {self._escape_rich_markup(path)}"
            elif hasattr(action, "content") and action.content:
                # For content-based actions, show truncated content
                content = str(action.content).strip().replace("\n", " ")
                if len(content) > 50:
                    content = content[:47] + "..."
                return f"{action_type}: {self._escape_rich_markup(content)}"
            elif hasattr(action, "message") and action.message:
                # For message actions, show truncated message
                msg = str(action.message).strip().replace("\n", " ")
                if len(msg) > 50:
                    msg = msg[:47] + "..."
                return f"{action_type}: {self._escape_rich_markup(msg)}"
            else:
                return f"{action_type} Action"

        elif hasattr(event, "observation") and event.observation is not None:
            # For ObservationEvents, try to get observation details
            obs = event.observation
            obs_type = obs.__class__.__name__.replace("Observation", "")

            if hasattr(obs, "content") and obs.content:
                content = str(obs.content).strip().replace("\n", " ")
                if len(content) > 50:
                    content = content[:47] + "..."
                return f"{obs_type}: {self._escape_rich_markup(content)}"
            else:
                return f"{obs_type} Observation"

        elif hasattr(event, "llm_message") and event.llm_message is not None:
            # For MessageEvents, show truncated message content
            msg = event.llm_message
            if hasattr(msg, "content") and msg.content:
                # Extract text from content list (content is a list of TextContent
                # objects)
                content_text = ""
                if isinstance(msg.content, list):
                    for content_item in msg.content:
                        if hasattr(content_item, "text"):
                            content_text += content_item.text + " "
                        elif hasattr(content_item, "content"):
                            content_text += str(content_item.content) + " "
                else:
                    content_text = str(msg.content)

                content_text = content_text.strip().replace("\n", " ")
                if len(content_text) > 60:
                    content_text = content_text[:57] + "..."
                role = "User" if msg.role == "user" else "Agent"
                return f"{role}: {self._escape_rich_markup(content_text)}"

        elif hasattr(event, "message") and event.message:
            # For events with direct message attribute
            content = str(event.message).strip().replace("\n", " ")
            if len(content) > 60:
                content = content[:57] + "..."
            return f"{fallback_title}: {self._escape_rich_markup(content)}"

        # If we can't extract meaningful info, try to truncate the visualized content
        if hasattr(event, "visualize"):
            try:
                import re

                # Convert Rich content to plain text for title
                content_str = str(event.visualize).strip().replace("\n", " ")
                # Remove ANSI codes and Rich markup
                content_str = re.sub(
                    r"\[/?[^\]]*\]", "", content_str
                )  # Remove Rich markup
                content_str = re.sub(
                    r"\x1b\[[0-9;]*m", "", content_str
                )  # Remove ANSI codes

                if len(content_str) > 60:
                    content_str = content_str[:57] + "..."

                if content_str.strip():
                    return f"{fallback_title}: {self._escape_rich_markup(content_str)}"
            except Exception:
                pass

        # Final fallback
        return fallback_title

    def _create_event_collapsible(self, event: Event) -> NonClickableCollapsible | None:
        """Create a Collapsible widget for the event with appropriate styling."""
        # Use the event's visualize property for content
        content = event.visualize

        if not content.plain.strip():
            return None

        # Don't emit system prompt in CLI
        if isinstance(event, SystemPromptEvent):
            return None
        elif isinstance(event, ActionEvent):
            # Check if action is None (non-executable)
            if event.action is None:
                title = self._extract_meaningful_title(
                    event, "Agent Action (Not Executed)"
                )
            else:
                title = self._extract_meaningful_title(event, "Agent Action")

            # Create content string with metrics subtitle if available
            content_string = str(content)
            metrics = self._format_metrics_subtitle()
            if metrics:
                content_string = f"{content_string}\n\n{metrics}"

            return NonClickableCollapsible(
                content_string,
                title=title,
                collapsed=False,  # Start expanded by default
                border_color=_get_event_border_color(event),
            )
        elif isinstance(event, ObservationEvent):
            title = self._extract_meaningful_title(event, "Observation")
            return NonClickableCollapsible(
                str(content),
                title=title,
                collapsed=False,  # Start expanded for observations
                border_color=_get_event_border_color(event),
            )
        elif isinstance(event, UserRejectObservation):
            title = self._extract_meaningful_title(event, "User Rejected Action")
            return NonClickableCollapsible(
                str(content),
                title=title,
                collapsed=False,  # Start expanded by default
                border_color=_get_event_border_color(event),
            )
        elif isinstance(event, MessageEvent):
            if (
                self._skip_user_messages
                and event.llm_message
                and event.llm_message.role == "user"
            ):
                return None
            assert event.llm_message is not None

            if event.llm_message.role == "user":
                title = self._extract_meaningful_title(event, "User Message")
            else:
                title = self._extract_meaningful_title(event, "Agent Message")

            # Create content string with metrics if available
            content_string = str(content)
            metrics = self._format_metrics_subtitle()
            if metrics and event.llm_message.role == "assistant":
                content_string = f"{content_string}\n\n{metrics}"

            return NonClickableCollapsible(
                content_string,
                title=title,
                collapsed=False,  # Start expanded by default
                border_color=_get_event_border_color(event),
            )
        elif isinstance(event, AgentErrorEvent):
            title = self._extract_meaningful_title(event, "Agent Error")
            content_string = str(content)
            metrics = self._format_metrics_subtitle()
            if metrics:
                content_string = f"{content_string}\n\n{metrics}"

            return NonClickableCollapsible(
                content_string,
                title=title,
                collapsed=False,  # Start expanded by default
                border_color=_get_event_border_color(event),
            )
        elif isinstance(event, PauseEvent):
            title = self._extract_meaningful_title(event, "User Paused")
            return NonClickableCollapsible(
                str(content),
                title=title,
                collapsed=False,  # Start expanded for pauses
                border_color=_get_event_border_color(event),
            )
        elif isinstance(event, Condensation):
            title = self._extract_meaningful_title(event, "Condensation")
            content_string = str(content)
            metrics = self._format_metrics_subtitle()
            if metrics:
                content_string = f"{content_string}\n\n{metrics}"

            return NonClickableCollapsible(
                content_string,
                title=title,
                collapsed=False,  # Start expanded for condensations
                border_color=_get_event_border_color(event),
            )
        else:
            # Fallback for unknown event types
            title = self._extract_meaningful_title(
                event, f"UNKNOWN Event: {event.__class__.__name__}"
            )
            content_string = f"{content}\n\nSource: {event.source}"
            return NonClickableCollapsible(
                content_string,
                title=title,
                collapsed=False,  # Start expanded for unknown events
                border_color=_get_event_border_color(event),
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
