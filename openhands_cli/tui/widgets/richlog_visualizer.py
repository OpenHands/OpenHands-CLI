"""
Textual-compatible visualizer for OpenHands conversation events.
This replaces the Rich-based CLIVisualizer with a Textual-compatible version.
"""

import re
import threading
from typing import TYPE_CHECKING

from rich.text import Text
from textual.widgets import Markdown

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
from openhands.sdk.event.condenser import Condensation, CondensationRequest
from openhands.sdk.event.conversation_error import ConversationErrorEvent
from openhands.sdk.tool.builtins.finish import FinishAction
from openhands.sdk.tool.builtins.think import ThinkAction
from openhands.tools.delegate.definition import DelegateAction
from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.task_tracker.definition import TaskTrackerObservation
from openhands.tools.terminal.definition import TerminalAction
from openhands_cli.shared.delegate_formatter import format_delegate_title
from openhands_cli.stores import CliSettings
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.widgets.collapsible import (
    Collapsible,
)


# Icons for different event types
SUCCESS_ICON = "✓"
ERROR_ICON = "✗"
AGENT_MESSAGE_PADDING = (1, 0, 1, 1)  # top, right, bottom, left

# Maximum line length for truncating titles/commands in collapsed view
MAX_LINE_LENGTH = 70
ELLIPSIS = "..."


if TYPE_CHECKING:
    from textual.containers import VerticalScroll
    from textual.widget import Widget

    from openhands_cli.tui.textual_app import OpenHandsApp


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
    elif isinstance(event, ConversationErrorEvent):
        return OPENHANDS_THEME.error or DEFAULT_COLOR
    elif isinstance(event, PauseEvent):
        return OPENHANDS_THEME.primary
    elif isinstance(event, Condensation):
        return "#727987"
    else:
        return DEFAULT_COLOR


class ConversationVisualizer(ConversationVisualizerBase):
    """Handles visualization of conversation events for Textual apps.

    This visualizer creates Collapsible widgets and adds them to a VerticalScroll
    container. Supports delegate visualization by tracking agent identity.
    """

    def __init__(
        self,
        container: "VerticalScroll",
        app: "OpenHandsApp",
        skip_user_messages: bool = False,
        name: str | None = None,
    ):
        """Initialize the visualizer.

        Args:
            container: The Textual VerticalScroll container to add widgets to
            app: The Textual app instance for thread-safe UI updates
            skip_user_messages: If True, skip displaying user messages
            name: Agent name to display in panel titles for delegation context.
                  When set, titles will be prefixed with the agent name.
        """
        super().__init__()
        self._container = container
        self._app = app
        self._skip_user_messages = skip_user_messages
        self._name = name
        # Store the main thread ID for thread safety checks
        self._main_thread_id = threading.get_ident()
        # Cache CLI settings to avoid repeated file system reads
        self._cli_settings: CliSettings | None = None
        # Track pending actions by tool_call_id for action-observation pairing
        self._pending_actions: dict[str, tuple[ActionEvent, Collapsible]] = {}

    @property
    def cli_settings(self) -> CliSettings:
        if self._cli_settings is None:
            self._cli_settings = CliSettings.load()
        return self._cli_settings

    def reload_configuration(self) -> None:
        self._cli_settings = CliSettings.load()

    def create_sub_visualizer(self, agent_id: str) -> "ConversationVisualizer":
        """Create a visualizer for a sub-agent during delegation.

        Creates a new ConversationVisualizer instance for the sub-agent that
        shares the same container and app, allowing delegate events to be
        rendered in the same TUI with agent-specific context.

        Args:
            agent_id: The identifier of the sub-agent being spawned

        Returns:
            A new ConversationVisualizer configured for the sub-agent
        """
        return ConversationVisualizer(
            container=self._container,
            app=self._app,
            skip_user_messages=self._skip_user_messages,
            name=agent_id,
        )

    @staticmethod
    def _format_agent_name(name: str) -> str:
        """Convert snake_case or camelCase agent name to Title Case for display.

        Args:
            name: Agent name in snake_case (e.g., "lodging_expert") or
                  camelCase (e.g., "MainAgent") or already formatted
                  (e.g., "Main Agent")

        Returns:
            Formatted name in Title Case (e.g., "Lodging Expert" or "Main Agent")

        Examples:
            >>> ConversationVisualizer._format_agent_name("lodging_expert")
            'Lodging Expert'
            >>> ConversationVisualizer._format_agent_name("MainAgent")
            'Main Agent'
            >>> ConversationVisualizer._format_agent_name("main_delegator")
            'Main Delegator'
            >>> ConversationVisualizer._format_agent_name("Main Agent")
            'Main Agent'
        """
        # If already has spaces, assume it's already formatted
        if " " in name:
            return name

        # Handle snake_case by replacing underscores with spaces
        if "_" in name:
            return name.replace("_", " ").title()

        # Handle camelCase/PascalCase by inserting spaces before capitals
        spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
        return spaced.title()

    def _get_formatted_agent_name(self) -> str:
        """Get the formatted agent name with 'Agent' suffix if needed.

        Returns:
            Formatted agent name with " Agent" suffix if name is set
            and doesn't already contain "agent", or just the formatted name.
            Returns empty string if no name is set.
        """
        if self._name:
            return self._format_agent_name_with_suffix(self._name)
        return ""

    def _format_agent_name_with_suffix(self, name: str) -> str:
        """Format an agent name and add 'Agent' suffix if needed.

        Args:
            name: The raw agent name to format.

        Returns:
            Formatted agent name with " Agent" suffix if name doesn't
            already contain "agent", or just the formatted name.
        """
        formatted_name = self._format_agent_name(name)
        # Don't add "Agent" suffix if name already contains "agent"
        if "agent" in formatted_name.lower():
            return formatted_name
        return f"{formatted_name} Agent"

    def _get_agent_prefix(self) -> str:
        """Get the agent name prefix for titles when in delegation context.

        Returns:
            Formatted agent name in parentheses like "(Agent Name) " if name is set,
            empty string otherwise.
        """
        agent_name = self._get_formatted_agent_name()
        if agent_name:
            return f"({agent_name}) "
        return ""

    def _run_on_main_thread(self, func, *args) -> None:
        """Run a function on the main thread via call_from_thread if needed."""
        if threading.get_ident() == self._main_thread_id:
            func(*args)
        else:
            self._app.call_from_thread(func, *args)

    def _do_refresh_plan_panel(self) -> None:
        """Refresh the plan panel (must be called from main thread)."""
        plan_panel = self._app.plan_panel
        auto_open = self.cli_settings.auto_open_plan_panel

        # Panel is already open, refresh contents
        if plan_panel.is_on_screen:
            plan_panel.refresh_from_disk()
            return

        # Not mounted: only open if user opted in
        # and hasn't dismissed it once already
        if not auto_open or plan_panel.user_dismissed:
            return

        # Open the plan panel
        plan_panel.toggle()

    def _get_agent_model(self) -> str | None:
        """Get the agent's model name from the conversation runner.

        Returns:
            The agent model name or None if not available.
        """
        try:
            if (
                self._app.conversation_runner
                and self._app.conversation_runner.conversation
                and hasattr(self._app.conversation_runner.conversation, "agent")
                and self._app.conversation_runner.conversation.agent  # type: ignore[union-attr]
            ):
                return self._app.conversation_runner.conversation.agent.llm.model  # type: ignore[union-attr]
        except Exception:
            pass
        return None

    def on_event(self, event: Event) -> None:
        """Main event handler that creates widgets for events."""
        # Check for TaskTrackerObservation to update/open the plan panel
        if isinstance(event, ObservationEvent) and isinstance(
            event.observation, TaskTrackerObservation
        ):
            self._run_on_main_thread(self._do_refresh_plan_panel)

        # Handle observation events by updating existing action collapsibles
        if isinstance(
            event, ObservationEvent | UserRejectObservation | AgentErrorEvent
        ):
            if self._handle_observation_event(event):
                return  # Successfully paired with action, no new widget needed

        widget = self._create_event_widget(event)
        if widget:
            self._run_on_main_thread(self._add_widget_to_ui, widget)

            # Add critic collapsible if present (for MessageEvent and ActionEvent)
            critic_result = getattr(event, "critic_result", None)
            if critic_result is not None and self.cli_settings.enable_critic:
                from openhands_cli.tui.utils.critic import (
                    create_critic_collapsible,
                    send_critic_inference_event,
                )
                from openhands_cli.tui.utils.critic.feedback import (
                    CriticFeedbackWidget,
                )

                # Get agent model for tracking
                agent_model = self._get_agent_model()
                conversation_id = str(self._app.conversation_id)

                # Send critic inference event to PostHog
                send_critic_inference_event(
                    critic_result=critic_result,
                    conversation_id=conversation_id,
                    agent_model=agent_model,
                )

                critic_widget = create_critic_collapsible(critic_result)
                self._run_on_main_thread(self._add_widget_to_ui, critic_widget)

                # Add feedback widget after critic collapsible
                feedback_widget = CriticFeedbackWidget(
                    critic_result=critic_result,
                    conversation_id=conversation_id,
                    agent_model=agent_model,
                )
                self._run_on_main_thread(self._add_widget_to_ui, feedback_widget)

    def _add_widget_to_ui(self, widget: "Widget") -> None:
        """Add a widget to the UI (must be called from main thread)."""
        self._container.mount(widget)
        # Automatically scroll to the bottom to show the newly added widget
        self._container.scroll_end(animate=False)

    def _update_widget_in_ui(
        self, collapsible: Collapsible, new_title: str, new_content: str
    ) -> None:
        """Update an existing widget in the UI (must be called from main thread)."""
        collapsible.update_title(new_title)
        collapsible.update_content(new_content)
        self._container.scroll_end(animate=False)

    def _handle_observation_event(
        self, event: ObservationEvent | UserRejectObservation | AgentErrorEvent
    ) -> bool:
        """Handle observation event by updating the corresponding action collapsible.

        Returns True if the observation was paired with an action, False otherwise.
        """
        tool_call_id = event.tool_call_id
        if tool_call_id not in self._pending_actions:
            return False

        action_event, collapsible = self._pending_actions.pop(tool_call_id)

        # Determine success/error status
        is_error = isinstance(event, UserRejectObservation | AgentErrorEvent)
        status_icon = ERROR_ICON if is_error else SUCCESS_ICON

        # Build the new title with status icon
        new_title = self._build_action_title(action_event)
        new_title = f"{new_title} {status_icon}"

        # Build the new content (observation result only)
        new_content = self._build_observation_content(event)

        self._run_on_main_thread(
            self._update_widget_in_ui, collapsible, new_title, new_content
        )
        return True

    def _build_action_title(self, event: ActionEvent) -> str:
        """Build a title for an action event.

        Format:
            "[Agent Prefix][bold]{summary}[/bold]" for most actions
            "[Agent Prefix][bold]{summary}[/bold][dim]: $ {command}[/dim]" for terminal
            "[Agent Prefix][bold]{summary}[/bold][dim]: {op} {path}[/dim]" for files

        The detail portion (after the colon) is rendered in dim style to
        visually distinguish it from the main summary text.

        When in delegation context (self._name is set), titles are prefixed
        with the agent name (e.g., "Lodging Expert Agent ").
        """
        agent_prefix = self._get_agent_prefix()
        summary = (
            self._escape_rich_markup(str(event.summary).strip().replace("\n", " "))
            if event.summary
            else ""
        )
        action = event.action

        # Terminal actions: show summary + command (truncated for display)
        if isinstance(action, TerminalAction) and action.command:
            cmd = self._escape_rich_markup(action.command.strip().replace("\n", " "))
            cmd = self._truncate_for_display(cmd)
            if summary:
                return f"{agent_prefix}[bold]{summary}[/bold][dim]: $ {cmd}[/dim]"
            return f"{agent_prefix}[dim]$ {cmd}[/dim]"

        # File operations: include path with Reading/Editing
        elif isinstance(action, FileEditorAction) and action.path:
            op = "Reading" if action.command == "view" else "Editing"
            path = self._escape_rich_markup(action.path)
            if summary:
                return f"{agent_prefix}[bold]{summary}[/bold][dim]: {op} {path}[/dim]"
            return f"{agent_prefix}[bold]{op}[/bold][dim] {path}[/dim]"

        # Delegate actions: show command and details
        if isinstance(action, DelegateAction):
            title = format_delegate_title(
                action.command,
                ids=action.ids,
                tasks=action.tasks,
                agent_types=action.agent_types,
                include_agent_types=True,
            )
            if summary:
                lower_title = title.lower()
                return f"{agent_prefix}[bold]{summary}[/bold][dim]: {lower_title}[/dim]"
            return f"{agent_prefix}[bold]{title}[/bold]"

        # All other actions: just use summary
        if summary:
            return f"{agent_prefix}[bold]{summary}[/bold]"
        return f"{agent_prefix}{event.tool_name}"

    def _build_observation_content(
        self, event: ObservationEvent | UserRejectObservation | AgentErrorEvent
    ) -> str:
        """Build content string from an observation event.

        Returns the Rich-formatted content to preserve colors and styling.
        """
        # Return the visualize content directly (Rich Text object)
        # The Collapsible widget can handle Rich renderables
        return str(event.visualize)

    def _escape_rich_markup(self, text: str) -> str:
        """Escape Rich markup characters in text to prevent markup errors.

        This is needed to handle content with special characters (e.g., Chinese text
        with brackets) that would otherwise cause MarkupError when rendered in
        Collapsible widgets with markup=True.
        """
        # Escape square brackets which are used for Rich markup
        return text.replace("[", r"\[").replace("]", r"\]")

    def _truncate_for_display(
        self, text: str, max_length: int = MAX_LINE_LENGTH, *, from_start: bool = True
    ) -> str:
        """Truncate text with ellipsis if it exceeds max_length.

        Args:
            text: The text to truncate.
            max_length: Maximum length before truncation.
            from_start: If True, keep the start and add ellipsis at end.
                       If False, keep the end and add ellipsis at start (for paths).
        """
        if len(text) > max_length:
            if from_start:
                return text[: max_length - len(ELLIPSIS)] + ELLIPSIS
            else:
                return ELLIPSIS + text[-(max_length - len(ELLIPSIS)) :]
        return text

    def _extract_meaningful_title(self, event, fallback_title: str) -> str:
        """Extract a meaningful title from an event, with fallback to truncated
        content."""
        # For ActionEvents, prefer the LLM-generated summary if available
        if hasattr(event, "summary") and event.summary:
            summary = str(event.summary).strip().replace("\n", " ")
            summary = self._truncate_for_display(summary)
            return self._escape_rich_markup(summary)

        # Try to extract meaningful information from the event
        if hasattr(event, "action") and event.action is not None:
            # For ActionEvents, try to get action type and details
            action = event.action
            action_type = action.__class__.__name__.replace("Action", "")

            # Try to get specific details based on action type
            if hasattr(action, "command") and action.command:
                # For command actions, show the command
                cmd = str(action.command).strip()
                cmd = self._truncate_for_display(cmd)
                return f"{action_type}: {self._escape_rich_markup(cmd)}"
            elif hasattr(action, "path") and action.path:
                # For file actions, show the path (truncate from start to show filename)
                path = str(action.path)
                path = self._truncate_for_display(path, from_start=False)
                return f"{action_type}: {self._escape_rich_markup(path)}"
            elif hasattr(action, "content") and action.content:
                # For content-based actions, show truncated content
                content = str(action.content).strip().replace("\n", " ")
                content = self._truncate_for_display(content)
                return f"{action_type}: {self._escape_rich_markup(content)}"
            elif hasattr(action, "message") and action.message:
                # For message actions, show truncated message
                msg = str(action.message).strip().replace("\n", " ")
                msg = self._truncate_for_display(msg)
                return f"{action_type}: {self._escape_rich_markup(msg)}"
            else:
                return f"{action_type} Action"

        elif hasattr(event, "observation") and event.observation is not None:
            # For ObservationEvents, try to get observation details
            obs = event.observation
            obs_type = obs.__class__.__name__.replace("Observation", "")

            if hasattr(obs, "content") and obs.content:
                content = str(obs.content).strip().replace("\n", " ")
                content = self._truncate_for_display(content)
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
                content_text = self._truncate_for_display(content_text)
                role = "User" if msg.role == "user" else "Agent"
                return f"{role}: {self._escape_rich_markup(content_text)}"

        elif hasattr(event, "message") and event.message:
            # For events with direct message attribute
            content = str(event.message).strip().replace("\n", " ")
            content = self._truncate_for_display(content)
            return f"{fallback_title}: {self._escape_rich_markup(content)}"

        # If we can't extract meaningful info, try to truncate the visualized content
        if hasattr(event, "visualize"):
            try:
                # Convert Rich content to plain text for title
                content_str = str(event.visualize).strip().replace("\n", " ")
                # Remove ANSI codes and Rich markup
                content_str = re.sub(
                    r"\[/?[^\]]*\]", "", content_str
                )  # Remove Rich markup
                content_str = re.sub(
                    r"\x1b\[[0-9;]*m", "", content_str
                )  # Remove ANSI codes

                content_str = self._truncate_for_display(content_str)

                if content_str.strip():
                    return f"{fallback_title}: {self._escape_rich_markup(content_str)}"
            except Exception:
                pass

        # Final fallback
        return fallback_title

    @property
    def _default_collapsed(self) -> bool:
        """Get the default collapsed state for new cells based on settings.

        Returns True if cells should start collapsed, False if expanded.
        """
        return not self.cli_settings.default_cells_expanded

    def _make_collapsible(
        self,
        content: str | Text,
        title: str,
        event: Event | None,
        collapsed: bool | None = None,
    ) -> Collapsible:
        """Create a Collapsible widget with standard settings.

        Args:
            content: The content to display (string or Rich Text object).
            title: The title for the collapsible header.
            event: The event used to determine border color (None for default).
            collapsed: Override the default collapsed state. If None, uses default.

        Returns:
            A configured Collapsible widget.
        """
        if collapsed is None:
            collapsed = self._default_collapsed
        border_color = _get_event_border_color(event) if event else "#888888"
        return Collapsible(
            content,
            title=title,
            collapsed=collapsed,
            border_color=border_color,
        )

    def _create_event_widget(self, event: Event) -> "Widget | None":
        """Create a widget for the event - either plain text or collapsible."""
        content = event.visualize

        # Don't emit system prompt in CLI
        if isinstance(event, SystemPromptEvent):
            return None
        # Don't emit condensation request events (internal events)
        elif isinstance(event, CondensationRequest):
            return None

        # Check if this is a plain text event (finish, think, or message)
        if isinstance(event, ActionEvent):
            action = event.action
            if isinstance(action, FinishAction):
                # For finish action, render as markdown with padding to align
                # User message has "padding: 0 1" and starts with "> ", so text
                # starts at position 3 (1 padding + 2 for "> ")
                # In delegation context, add agent header
                message = str(action.message)
                if self._name:
                    agent_name = self._get_formatted_agent_name()
                    message = f"**{agent_name}:**\n\n{message}"
                widget = Markdown(message)
                widget.styles.padding = AGENT_MESSAGE_PADDING
                return widget
            elif isinstance(action, ThinkAction):
                # For think action, render as markdown with padding
                widget = Markdown(str(action.visualize))
                widget.styles.padding = AGENT_MESSAGE_PADDING
                return widget

        if isinstance(event, MessageEvent):
            if not event.llm_message:
                return None

            # Skip direct user messages (they are displayed separately in the UI)
            # This applies both when skip_user_messages is set, and for user messages
            # without a sender in delegation context
            if event.llm_message.role == "user" and not event.sender:
                return None

            # Case 1: Delegation message (both sender and name are set)
            # Format with arrow notation showing sender → receiver
            if event.sender and self._name:
                message_content = str(content)
                agent_name = self._get_formatted_agent_name()
                event_sender = self._format_agent_name_with_suffix(event.sender)

                if event.llm_message.role == "user":
                    # Message from another agent (via delegation)
                    prefix = f"**{event_sender} → {agent_name}:**\n\n"
                else:
                    # Agent message - derive recipient from sender context
                    prefix = f"**{agent_name} → {event_sender}:**\n\n"

                message_content = prefix + message_content
                widget = Markdown(message_content)
                widget.styles.padding = AGENT_MESSAGE_PADDING
                return widget

            # Case 2: Regular agent message (name set, no sender, assistant role)
            # This is the normal case for agent responses in the main conversation
            # Fixes GitHub issue #399: Agent MessageEvents were being silently dropped
            if self._name and event.llm_message.role == "assistant":
                widget = Markdown(str(content))
                widget.styles.padding = AGENT_MESSAGE_PADDING
                return widget

            # Case 3: No name context - skip MessageEvents
            # (visualizer without name is typically not used in CLI)
            if not self._name:
                return None

        # For other events, use collapsible
        return self._create_event_collapsible(event)

    def _create_event_collapsible(self, event: Event) -> Collapsible | None:
        """Create a Collapsible widget for the event with appropriate styling.

        When in delegation context (self._name is set), titles are prefixed
        with the agent name (e.g., "Lodging Expert Agent Observation").
        """
        # Use the event's visualize property for content
        content = event.visualize

        if not content.plain.strip():
            return None

        agent_prefix = self._get_agent_prefix()

        # Don't emit system prompt in CLI
        if isinstance(event, SystemPromptEvent):
            return None
        # Don't emit condensation request events (internal events)
        elif isinstance(event, CondensationRequest):
            return None
        elif isinstance(event, ActionEvent):
            # Build title using new format with agent prefix
            title = self._build_action_title(event)
            content_string = self._escape_rich_markup(str(content))

            # Action events default to collapsed since we have summary in title
            collapsible = self._make_collapsible(content_string, title, event)

            # Store for pairing with observation
            self._pending_actions[event.tool_call_id] = (event, collapsible)

            return collapsible
        elif isinstance(event, ObservationEvent):
            # If we get here, the observation wasn't paired with an action
            # (shouldn't happen normally, but handle gracefully)
            title = self._extract_meaningful_title(event, "Observation")
            return self._make_collapsible(
                self._escape_rich_markup(str(content)), f"{agent_prefix}{title}", event
            )
        elif isinstance(event, UserRejectObservation):
            title = self._extract_meaningful_title(event, "User Rejected Action")
            return self._make_collapsible(
                self._escape_rich_markup(str(content)), f"{agent_prefix}{title}", event
            )
        elif isinstance(event, AgentErrorEvent):
            title = self._extract_meaningful_title(event, "Agent Error")
            content_string = self._escape_rich_markup(str(content))
            return self._make_collapsible(
                content_string, f"{agent_prefix}{title}", event
            )
        elif isinstance(event, ConversationErrorEvent):
            title = self._extract_meaningful_title(event, "Conversation Error")
            content_string = self._escape_rich_markup(str(content))
            return self._make_collapsible(
                content_string, f"{agent_prefix}{title}", event
            )
        elif isinstance(event, PauseEvent):
            title = self._extract_meaningful_title(event, "User Paused")
            return self._make_collapsible(
                self._escape_rich_markup(str(content)), f"{agent_prefix}{title}", event
            )
        elif isinstance(event, Condensation):
            title = self._extract_meaningful_title(event, "Condensation")
            content_string = self._escape_rich_markup(str(content))
            return self._make_collapsible(
                content_string, f"{agent_prefix}{title}", event
            )
        else:
            # Fallback for unknown event types
            title = self._extract_meaningful_title(
                event, f"UNKNOWN Event: {event.__class__.__name__}"
            )
            content_string = (
                f"{self._escape_rich_markup(str(content))}\n\nSource: {event.source}"
            )
            return self._make_collapsible(
                content_string, f"{agent_prefix}{title}", event
            )
