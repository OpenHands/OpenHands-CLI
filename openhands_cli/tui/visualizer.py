"""CLI-specific visualization configuration.

This module customizes the SDK's default visualizer for CLI usage by:
- Skipping SystemPromptEvent (only relevant for SDK internals)
- Truncating long command outputs and agent responses
- Storing truncated content for /full command access
"""

from typing import TYPE_CHECKING

from openhands.sdk.conversation.visualizer.default import (
    EVENT_VISUALIZATION_CONFIG,
    DefaultConversationVisualizer,
    EventVisualizationConfig,
)
from openhands.sdk.event import MessageEvent, ObservationEvent, SystemPromptEvent

from openhands_cli.tui.tui import DEFAULT_COMMAND_OUTPUT_LINES

if TYPE_CHECKING:
    from rich.console import RenderableType
    from rich.panel import Panel
    from rich.text import Text

# Module-level variable to store the current visualizer instance
_current_visualizer: "CLIVisualizer | None" = None


def get_current_visualizer() -> "CLIVisualizer | None":
    """Get the current visualizer instance.

    Returns:
        The current CLIVisualizer instance, or None if not set.
    """
    return _current_visualizer


class CLIVisualizer(DefaultConversationVisualizer):
    """Custom visualizer that truncates long outputs for CLI display."""

    def __init__(self):
        """Initialize the visualizer with storage for truncated content."""
        super().__init__()
        self._last_full_content: str | None = None
        # Store this instance globally
        global _current_visualizer
        _current_visualizer = self

    def get_last_full_content(self) -> str | None:
        """Get the last truncated full content.

        Returns:
            The full content that was last truncated, or None if no content was truncated.
        """
        return self._last_full_content

    def _create_event_block(self, event) -> "RenderableType | None":
        """Override to truncate ObservationEvent and MessageEvent (assistant only).

        Args:
            event: The event to visualize.

        Returns:
            The rendered block, or None if the event should be skipped.
        """
        # Call parent to get the base block
        block = super()._create_event_block(event)

        if block is None:
            return None

        # Truncate ObservationEvent (command outputs)
        if isinstance(event, ObservationEvent):
            block, was_truncated = self._truncate_long_text_in_block(
                block, DEFAULT_COMMAND_OUTPUT_LINES
            )
            if was_truncated:
                # Store the full content from the event's visualization
                try:
                    self._last_full_content = str(event.visualize.plain)
                except Exception:
                    self._last_full_content = None
            return block

        # Truncate MessageEvent (agent text responses, role="assistant" only)
        if isinstance(event, MessageEvent):
            # Only truncate assistant messages
            if hasattr(event, "llm_message") and event.llm_message.role == "assistant":
                block, was_truncated = self._truncate_long_text_in_block(
                    block, DEFAULT_COMMAND_OUTPUT_LINES
                )
                if was_truncated:
                    # Store the full content from the event's visualization
                    try:
                        self._last_full_content = str(event.visualize.plain)
                    except Exception:
                        self._last_full_content = None
                return block

        return block

    def _truncate_long_text_in_block(
        self, block: "RenderableType", max_lines: int
    ) -> tuple["RenderableType", bool]:
        """Recursively find and truncate long Text objects in Rich block structures.

        Handles Text, Group, Panel, and other Rich objects.

        Args:
            block: The Rich renderable block to process.
            max_lines: Maximum number of lines to show before truncation.

        Returns:
            A tuple of (modified_block, was_truncated).
        """
        from rich.console import Group
        from rich.panel import Panel
        from rich.text import Text

        was_truncated = False

        # Handle Text objects directly
        if isinstance(block, Text):
            lines = str(block).split("\n")
            if len(lines) > max_lines:
                truncated_lines = lines[:max_lines]
                remaining = len(lines) - max_lines

                # Create truncated text
                truncated_text = Text("\n".join(truncated_lines))
                truncated_text.append(
                    f"\n... and {remaining} more line{'s' if remaining != 1 else ''}",
                    style="dim italic",
                )
                truncated_text.append(
                    "\n(use /full to see complete output)", style="dim italic"
                )

                # Preserve original styling if possible
                if hasattr(block, "style"):
                    truncated_text.stylize(block.style, 0, len(truncated_text))

                self._last_full_content = "\n".join(lines)
                return truncated_text, True

        # Handle Panel objects
        elif isinstance(block, Panel):
            # Recursively process the panel's renderable
            new_renderable, truncated = self._truncate_long_text_in_block(
                block.renderable, max_lines
            )

            if truncated:
                was_truncated = True
                # Update panel title to show line count
                original_title = block.title or ""
                if isinstance(new_renderable, Text):
                    total_lines = len(str(self._last_full_content or "").split("\n"))
                    shown_lines = max_lines
                    title = f"{original_title} (showing {shown_lines} of {total_lines} lines)"
                else:
                    title = original_title

                # Create new panel with updated title and renderable
                new_panel = Panel(
                    new_renderable,
                    title=title,
                    border_style=block.border_style,
                    box=block.box,
                    padding=block.padding,
                    style=block.style,
                )
                return new_panel, True

        # Handle Group objects
        elif isinstance(block, Group):
            new_renderables = []
            for renderable in block.renderables:
                new_renderable, truncated = self._truncate_long_text_in_block(
                    renderable, max_lines
                )
                if truncated:
                    was_truncated = True
                new_renderables.append(new_renderable)

            if was_truncated:
                return Group(*new_renderables), True

        # For other types, try to process if they have renderables
        elif hasattr(block, "renderables"):
            new_renderables = []
            for renderable in block.renderables:
                new_renderable, truncated = self._truncate_long_text_in_block(
                    renderable, max_lines
                )
                if truncated:
                    was_truncated = True
                new_renderables.append(new_renderable)

            if was_truncated:
                # Try to create a new instance with updated renderables
                try:
                    new_block = type(block)(*new_renderables)
                    return new_block, True
                except Exception:
                    pass

        return block, False


# CLI-specific customization: skip SystemPromptEvent
# (not needed in CLI output, only relevant for SDK internals)
EVENT_VISUALIZATION_CONFIG[SystemPromptEvent] = EventVisualizationConfig(
    **{**EVENT_VISUALIZATION_CONFIG[SystemPromptEvent].model_dump(), "skip": True}
)

__all__ = ["CLIVisualizer", "get_current_visualizer"]
