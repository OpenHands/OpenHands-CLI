"""Minimal textual app for OpenHands CLI migration.

This is the starting point for migrating from prompt_toolkit to textual.
It creates a basic app with:
- A scrollable main display (RichLog) that shows the splash screen initially
- An Input widget at the bottom for user messages
- A status line showing timer and work directory
- The splash screen content scrolls off as new messages are added
"""

import asyncio
import uuid
from collections.abc import Iterable
from typing import ClassVar

from textual import events, getters, on
from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import Screen
from textual.signal import Signal
from textual.widgets import Footer, Input, Static, TextArea
from textual_autocomplete import AutoComplete

from openhands.sdk import BaseConversation
from openhands.sdk.event import ActionEvent
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmationPolicyBase,
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.risk import SecurityRisk
from openhands_cli.conversations.store.local import LocalFileStore
from openhands_cli.locations import get_conversations_dir
from openhands_cli.stores import AgentStore, MissingEnvironmentVariablesError
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.splash import get_splash_content
from openhands_cli.tui.core.commands import is_valid_command, show_help
from openhands_cli.tui.core.conversation_manager import ConversationManager
from openhands_cli.tui.core.conversation_runner import ConversationRunner
from openhands_cli.tui.core.messages import (
    ConfirmationNeeded,
    ConfirmationProvided,
    ConversationCreated,
    ConversationSwitched,
    ConversationTitleUpdated,
    RevertSelectionRequest,
    SwitchConversationRequest,
)
from openhands_cli.tui.modals import SettingsScreen
from openhands_cli.tui.modals.confirmation_modal import ConfirmationSettingsModal
from openhands_cli.tui.modals.exit_modal import ExitConfirmationModal
from openhands_cli.tui.panels.confirmation_panel import InlineConfirmationPanel
from openhands_cli.tui.panels.history_side_panel import HistorySidePanel
from openhands_cli.tui.panels.mcp_side_panel import MCPSidePanel
from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel
from openhands_cli.tui.widgets import InputField
from openhands_cli.tui.widgets.collapsible import (
    Collapsible,
    CollapsibleNavigationMixin,
    CollapsibleTitle,
)
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer
from openhands_cli.tui.widgets.status_line import (
    InfoStatusLine,
    WorkingStatusLine,
)
from openhands_cli.user_actions.types import UserConfirmation
from openhands_cli.utils import json_callback


class OpenHandsApp(CollapsibleNavigationMixin, App):
    """A minimal textual app for OpenHands CLI with scrollable main display."""

    # Key bindings
    BINDINGS: ClassVar = [
        ("ctrl+l", "toggle_input_mode", "Toggle single/multi-line input"),
        ("ctrl+o", "toggle_cells", "Toggle Cells"),
        ("ctrl+j", "submit_textarea", "Submit multi-line input"),
        ("escape", "pause_conversation", "Pause the conversation"),
        ("ctrl+q", "request_quit", "Quit the application"),
        ("ctrl+c", "request_quit", "Quit the application"),
        ("ctrl+d", "request_quit", "Quit the application"),
    ]

    input_field: getters.query_one[InputField] = getters.query_one(InputField)
    main_display: getters.query_one[VerticalScroll] = getters.query_one("#main_display")
    content_area: getters.query_one[Horizontal] = getters.query_one("#content_area")

    def __init__(
        self,
        exit_confirmation: bool = True,
        resume_conversation_id: uuid.UUID | None = None,
        queued_inputs: list[str] | None = None,
        initial_confirmation_policy: ConfirmationPolicyBase | None = None,
        headless_mode: bool = False,
        json_mode: bool = False,
        env_overrides_enabled: bool = False,
        critic_disabled: bool = False,
        **kwargs,
    ):
        """Initialize the app with custom OpenHands theme.

        Args:
            exit_confirmation: If True, show confirmation modal before exit.
                             If False, exit immediately.
            resume_conversation_id: Optional conversation ID to resume.
            queued_inputs: Optional list of input strings to queue at the start.
            initial_confirmation_policy: Initial confirmation policy to use.
                                       If None, defaults to AlwaysConfirm.
            headless_mode: If True, run in headless mode.
            json_mode: If True, enable JSON output mode.
            env_overrides_enabled: If True, environment variables will override
                                   stored LLM settings.
            critic_disabled: If True, critic functionality will be disabled.
        """
        super().__init__(**kwargs)

        self.conversation_running_signal = Signal(self, "conversation_running_signal")
        self.is_ui_initialized = False

        # Store exit confirmation setting
        self.exit_confirmation = exit_confirmation

        # Store headless mode setting for auto-exit behavior
        self.headless_mode = headless_mode

        # Store JSON mode setting
        self.json_mode = json_mode

        # Store agent loading options
        self.env_overrides_enabled = env_overrides_enabled
        self.critic_disabled = critic_disabled

        # Store resume conversation ID
        self.conversation_id = (
            resume_conversation_id if resume_conversation_id else uuid.uuid4()
        )
        self.conversation_dir = BaseConversation.get_persistence_dir(
            get_conversations_dir(), self.conversation_id
        )

        # Store queued inputs (copy to prevent mutating caller's list)
        self.pending_inputs = list(queued_inputs) if queued_inputs else []

        # Store initial confirmation policy
        self.initial_confirmation_policy = (
            initial_confirmation_policy or AlwaysConfirm()
        )

        # Initialize conversation runner (updated with write callback in on_mount)
        self.conversation_runner = None
        self._store = LocalFileStore()
        self._conversation_manager = ConversationManager(self, self._store)
        self._reload_visualizer = (
            lambda: self.conversation_runner.visualizer.reload_configuration()
            if self.conversation_runner
            else None
        )

        # Confirmation panel tracking
        self.confirmation_panel: InlineConfirmationPanel | None = None

        # MCP panel tracking
        self.mcp_panel: MCPSidePanel | None = None

        self.plan_panel: PlanSidePanel = PlanSidePanel(self)

        # Register the custom theme
        self.register_theme(OPENHANDS_THEME)

        # Set the theme as active
        self.theme = "openhands"

    CSS_PATH = "textual_app.tcss"

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        # Content area - horizontal layout for main display and optional confirmation
        with Horizontal(id="content_area"):
            # Main scrollable display - using VerticalScroll to support Collapsible
            with VerticalScroll(id="main_display"):
                # Add initial splash content as individual widgets
                yield Static(id="splash_banner", classes="splash-banner")
                yield Static(id="splash_version", classes="splash-version")
                yield Static(id="splash_status", classes="status-panel")
                yield Static(id="splash_conversation", classes="conversation-panel")
                yield Static(
                    id="splash_instructions_header", classes="splash-instruction-header"
                )
                yield Static(id="splash_instructions", classes="splash-instruction")
                yield Static(id="splash_update_notice", classes="splash-update-notice")
                yield Static(id="splash_critic_notice", classes="splash-critic-notice")

            # Input area - docked to bottom
            with Container(id="input_area"):
                yield WorkingStatusLine(self)
                yield InputField(
                    placeholder="Type your message, @mention a file, or / for commands"
                )

                yield InfoStatusLine(self)

        # Footer - shows available key bindings
        yield Footer()

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "History",
            "Toggle conversation history panel",
            self.action_toggle_history,
        )
        yield SystemCommand(
            "MCP", "View MCP configurations", lambda: MCPSidePanel.toggle(self)
        )
        yield SystemCommand(
            "Plan",
            "View agent plan",
            lambda: self.plan_panel.toggle(),
        )
        yield SystemCommand("Settings", "Configure settings", self.action_open_settings)

    def on_mount(self) -> None:
        """Called when app starts."""
        from openhands_cli.stores import MissingEnvironmentVariablesError

        # Subscribe to conversation running signal for auto-exit in headless mode
        self.conversation_running_signal.subscribe(
            self, self._on_conversation_state_changed
        )

        # Check if user has existing settings
        try:
            initial_setup_required = SettingsScreen.is_initial_setup_required(
                env_overrides_enabled=self.env_overrides_enabled
            )
        except MissingEnvironmentVariablesError as e:
            # Store the error to be re-raised after clean exit
            self._missing_env_vars_error = e
            self.exit()
            return

        if initial_setup_required:
            # In headless mode we cannot open interactive settings.
            if self.headless_mode:
                from rich.console import Console

                console = Console()
                console.print(
                    f"[{OPENHANDS_THEME.error}]Headless mode requires existing "
                    f"settings.[/{OPENHANDS_THEME.error}]\n"
                    f"[bold]Please run:[/bold] [{OPENHANDS_THEME.success}]openhands"
                    f"[/{OPENHANDS_THEME.success}] to configure your settings "
                    f"before using [{OPENHANDS_THEME.accent}]--headless"
                    f"[/{OPENHANDS_THEME.accent}]."
                )
                self.exit()
                return

            # No existing settings - show settings screen first
            self._show_initial_settings()
            return

        # User has settings - proceed with normal startup
        self._initialize_main_ui()

    def _show_initial_settings(self) -> None:
        """Show settings screen for first-time users."""
        settings_screen = SettingsScreen(
            on_settings_saved=[
                self._initialize_main_ui,
                self._reload_visualizer,
            ],
            on_first_time_settings_cancelled=self._handle_initial_setup_cancelled,
            env_overrides_enabled=self.env_overrides_enabled,
        )
        self.push_screen(settings_screen)

    def _handle_initial_setup_cancelled(self) -> None:
        """Handle when initial setup is cancelled - show settings again."""
        # For first-time users, cancelling should loop back to settings
        # This creates the loop until they either save settings or exit
        exit_modal = ExitConfirmationModal(
            on_exit_confirmed=lambda: self.app.exit(),
            on_exit_cancelled=self._show_initial_settings,
        )
        self.app.push_screen(exit_modal)

    def _on_conversation_state_changed(self, is_running: bool) -> None:
        """Handle conversation state changes for auto-exit in headless mode."""
        # If conversation just finished and we're in headless mode, exit
        if not is_running and self.headless_mode:
            self._print_conversation_summary()
            self.exit()

    def _print_conversation_summary(self) -> None:
        """Print conversation summary for headless mode."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.rule import Rule

        console = Console()

        if not self.conversation_runner:
            return

        num_agent_messages, last_agent_message = (
            self.conversation_runner.get_conversation_summary()
        )

        console.print()  # blank line
        console.print(Rule("CONVERSATION SUMMARY"))

        console.print(f"[bold]Number of agent messages:[/bold] {num_agent_messages}")

        console.print("[bold]Last message sent by the agent:[/bold]")
        console.print(
            Panel(
                last_agent_message,
                expand=False,
                border_style="cyan",
                title="Agent",
                title_align="left",
            )
        )

        console.print(Rule())

    def action_open_settings(self) -> None:
        """Action to open the settings screen."""
        # Check if conversation is running
        if self.conversation_runner and self.conversation_runner.is_running:
            self.notify(
                "Settings are not available while a conversation is running. "
                "Please wait for the current conversation to complete.",
                severity="warning",
                timeout=5.0,
            )
            return

        # Open the settings screen for existing users
        settings_screen = SettingsScreen(
            on_settings_saved=[
                self._reload_visualizer,
                self._notify_restart_required,
            ],
            env_overrides_enabled=self.env_overrides_enabled,
        )
        self.push_screen(settings_screen)

    def _notify_restart_required(self) -> None:
        """Notify user that CLI restart is required for agent settings changes.

        Only shows notification if a conversation runner has been instantiated,
        meaning a conversation has already started with the previous settings.

        Note: This callback is only registered for `action_open_settings` (existing
        users), not for `_show_initial_settings` (first-time setup). Additionally,
        during first-time setup, conversation_runner is always None, so even if
        this method were called, no notification would be shown.
        """
        if self.conversation_runner:
            self.notify(
                "Settings saved. Please restart the CLI for changes to take effect.",
                severity="information",
                timeout=10.0,
            )

    def _initialize_main_ui(self) -> None:
        """Initialize the main UI components."""

        if self.is_ui_initialized:
            return

        # Check if agent has critic configured
        has_critic = False
        try:
            agent_store = AgentStore()
            agent = agent_store.load_or_create(
                env_overrides_enabled=self.env_overrides_enabled,
                critic_disabled=self.critic_disabled,
            )
            if agent:
                has_critic = agent.critic is not None
        except Exception:
            # If we can't load agent, just continue without critic notice
            pass

        # Get structured splash content
        splash_content = get_splash_content(
            conversation_id=self.conversation_id.hex,
            theme=OPENHANDS_THEME,
            has_critic=has_critic,
        )

        # Update individual splash widgets
        self.query_one("#splash_banner", Static).update(splash_content["banner"])
        self.query_one("#splash_version", Static).update(splash_content["version"])
        self.query_one("#splash_status", Static).update(splash_content["status_text"])
        self.query_one("#splash_conversation", Static).update(
            splash_content["conversation_text"]
        )
        self.query_one("#splash_instructions_header", Static).update(
            splash_content["instructions_header"]
        )

        # Join instructions into a single string
        instructions_text = "\n".join(splash_content["instructions"])
        self.query_one("#splash_instructions", Static).update(instructions_text)

        # Update notice (hide if None)
        update_notice_widget = self.query_one("#splash_update_notice", Static)
        if splash_content["update_notice"]:
            update_notice_widget.update(splash_content["update_notice"])
            update_notice_widget.display = True
        else:
            update_notice_widget.display = False

        # Update critic notice (hide if None)
        critic_notice_widget = self.query_one("#splash_critic_notice", Static)
        if splash_content["critic_notice"]:
            critic_notice_widget.update(splash_content["critic_notice"])
            critic_notice_widget.display = True
        else:
            critic_notice_widget.display = False

        # Process any queued inputs
        self._process_queued_inputs()
        self.is_ui_initialized = True

    def create_conversation_runner(
        self,
        conversation_id: uuid.UUID | None = None,
        visualizer: ConversationVisualizer | None = None,
    ) -> ConversationRunner:
        """Create a ConversationRunner for a given conversation id.

        Args:
            conversation_id: Conversation id to use. Defaults to current id.
            visualizer: Optional visualizer. If not provided, a new one is created.
        """
        conversation_uuid = conversation_id or self.conversation_id

        # Initialize conversation runner with visualizer that can add widgets.
        # Skip user messages since we display them immediately in the UI.
        conversation_visualizer = visualizer or ConversationVisualizer(
            self.main_display, self, skip_user_messages=True, name="OpenHands Agent"
        )

        # Create JSON callback if in JSON mode
        event_callback = None
        if self.json_mode:
            event_callback = json_callback

        runner = ConversationRunner(
            conversation_uuid,
            self.conversation_running_signal.publish,
            self,  # Pass app for posting messages
            lambda title, message, severity: (
                self.notify(title=title, message=message, severity=severity)
            ),
            conversation_visualizer,
            self.initial_confirmation_policy,
            event_callback,
            env_overrides_enabled=self.env_overrides_enabled,
            critic_disabled=self.critic_disabled,
        )

        return runner

    def _process_queued_inputs(self) -> None:
        """Process any queued inputs from --task or --file arguments.

        Currently processes only the first queued input immediately.
        In the future, this could be extended to process multiple instructions
        from the queue one by one as the agent completes each task.
        """
        if not self.pending_inputs:
            return

        # Process the first queued input immediately
        user_input = self.pending_inputs.pop(0)

        # Add the user message to the main display as a Static widget
        user_message_widget = Static(
            f"> {user_input}", classes="user-message", markup=False
        )
        self.main_display.mount(user_message_widget)
        self.main_display.scroll_end(animate=False)

        # Handle the message asynchronously
        asyncio.create_task(self._handle_user_message(user_input))

    @on(InputField.Submitted)
    async def handle_user_input(self, message: InputField.Submitted) -> None:
        content = message.content.strip()
        if not content:
            return

        # Add the user message to the main display as a Static widget
        user_message_widget = Static(
            f"> {content}", classes="user-message", markup=False
        )
        await self.main_display.mount(user_message_widget)
        self.main_display.scroll_end(animate=False)
        # Force immediate refresh to show the message without delay
        self.refresh()

        # Handle commands - only exact matches
        if is_valid_command(content):
            self._handle_command(content)
        else:
            # Handle regular messages with conversation runner
            await self._handle_user_message(content)

    def _handle_command(self, command: str) -> None:
        """Handle command execution."""

        if command == "/help":
            show_help(self.main_display)
        elif command == "/new":
            self._handle_new_command()
        elif command == "/history":
            self._handle_history_command()
        elif command == "/confirm":
            self._handle_confirm_command()
        elif command == "/condense":
            self._handle_condense_command()
        elif command == "/feedback":
            self._handle_feedback_command()
        elif command == "/exit":
            self._handle_exit()
        else:
            self.notify(
                title="Command error",
                message=f"Unknown command: {command}",
                severity="error",
            )

    async def _handle_user_message(self, user_message: str) -> None:
        """Handle regular user messages with the conversation runner."""
        # Dismiss any pending critic feedback widgets when user sends a new message
        self._dismiss_pending_feedback_widgets()

        # Check if conversation runner is initialized
        if self.conversation_runner is None:
            self.conversation_runner = self.create_conversation_runner()

        # If History panel is open, update "New conversation" title immediately
        # on the first message (without waiting for persistence on disk).
        self._conversation_manager.update_title(user_message)

        # Block new messages while waiting for confirmation
        if self.conversation_runner.is_waiting_for_confirmation:
            self.notify(
                title="Confirmation Required",
                message="Please confirm or reject the pending action before "
                "sending a new message.",
                severity="warning",
            )
            return

        # Show that we're processing the message
        if self.conversation_runner.is_running:
            await self.conversation_runner.queue_message(user_message)
            return

        # Process message asynchronously to keep UI responsive
        # Only run worker if we have an active app (not in tests)
        try:
            self.run_worker(
                self.conversation_runner.process_message_async(
                    user_message, self.headless_mode
                ),
                name="process_message",
            )
        except RuntimeError:
            # In test environment, just show a placeholder message
            placeholder_widget = Static(
                f"[{OPENHANDS_THEME.success}]Message would be processed by "
                f"conversation runner[/{OPENHANDS_THEME.success}]",
                classes="status-message",
            )
            self.main_display.mount(placeholder_widget)
            self.main_display.scroll_end(animate=False)

    def action_request_quit(self) -> None:
        """Action to handle Ctrl+Q key binding."""
        self._handle_exit()

    def action_toggle_cells(self) -> None:
        """Action to handle Ctrl+O key binding.

        Collapses all cells if any are expanded, otherwise expands all cells.
        This provides a quick way to minimize or maximize all content at once.
        """
        collapsibles = self.main_display.query(Collapsible)

        # If any cell is expanded, collapse all; otherwise expand all
        any_expanded = any(not collapsible.collapsed for collapsible in collapsibles)

        for collapsible in collapsibles:
            collapsible.collapsed = any_expanded

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard navigation.

        - Auto-focus input when user starts typing (allows clicking cells without
          losing typing context)
        - When Tab is pressed from input area, focus the most recent (last) cell
          instead of the first one (unless autocomplete is showing)
        """
        # Handle Tab from input area - focus most recent cell
        # Skip if autocomplete dropdown is visible (Tab is used for selection)
        if event.key == "tab" and isinstance(self.focused, Input | TextArea):
            if not self._is_autocomplete_showing():
                collapsibles = list(self.main_display.query(Collapsible))
                if collapsibles:
                    # Focus the last (most recent) collapsible's title
                    last_collapsible = collapsibles[-1]
                    last_title = last_collapsible.query_one(CollapsibleTitle)
                    last_title.focus()
                    last_collapsible.scroll_visible()
                    event.stop()
                    event.prevent_default()
                    return

        # Auto-focus input when user types printable characters
        if event.is_printable and not isinstance(self.focused, Input | TextArea):
            self.input_field.focus_input()

    def _is_autocomplete_showing(self) -> bool:
        """Check if the autocomplete dropdown is currently visible.

        This prevents Tab key interception when user wants to select an
        autocomplete suggestion.
        """
        autocompletes = self.query(AutoComplete)
        return any(ac.display for ac in autocompletes)

    def on_mouse_up(self, _event: events.MouseUp) -> None:
        """Handle mouse up events for auto-copy on text selection.

        When the user finishes selecting text by releasing the mouse button,
        this method checks if there's selected text and copies it to clipboard.
        """
        # Get selected text from the screen
        selected_text = self.screen.get_selected_text()
        if not selected_text:
            return

        # Copy to clipboard and get result
        pyperclip_success = self._copy_to_clipboard(selected_text)

        # Show appropriate notification based on copy result
        if pyperclip_success:
            self.notify(
                "Selection copied to clipboard",
                title="Auto-copy",
                timeout=2,
            )
        elif self._is_linux():
            # On Linux without pyperclip working, OSC 52 may or may not work
            self.notify(
                "Selection copied. May require `sudo apt install xclip`",
                title="Auto-copy",
                timeout=4,
            )
        else:
            self.notify(
                "Selection copied to clipboard",
                title="Auto-copy",
                timeout=2,
            )

    def _is_linux(self) -> bool:
        """Check if the current platform is Linux."""
        import platform

        return platform.system() == "Linux"

    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard using pyperclip with OSC 52 fallback.

        Uses a two-layer approach for clipboard access:
        1. Primary: pyperclip for direct OS clipboard access
        2. Fallback: Textual's copy_to_clipboard (OSC 52 escape sequence)

        This ensures clipboard works across different terminal environments.

        Returns:
            True if pyperclip succeeded, False otherwise.
        """
        import pyperclip

        pyperclip_success = False
        # Primary: Try pyperclip for direct OS clipboard access
        try:
            pyperclip.copy(text)
            pyperclip_success = True
        except pyperclip.PyperclipException:
            # pyperclip failed - will try OSC 52 fallback
            pass

        # Also try OSC 52 - this doesn't raise errors, it just sends escape
        # sequences. We do both because pyperclip and OSC 52 can target
        # different clipboards (e.g., remote terminals, tmux, SSH sessions)
        self.copy_to_clipboard(text)

        return pyperclip_success

    def action_pause_conversation(self) -> None:
        """Action to handle Esc key binding - pause the running conversation."""
        # Run the pause operation asynchronously to avoid blocking the UI
        if self.conversation_runner:
            self.conversation_runner.pause_runner_without_blocking()
        else:
            self.notify(message="No running conversation to pause", severity="error")

    def _handle_confirm_command(self) -> None:
        """Handle the /confirm command to show confirmation settings modal."""
        if not self.conversation_runner:
            # If no conversation runner, create one to get the current policy
            self.conversation_runner = self.create_conversation_runner()

        # Get current confirmation policy
        current_policy = self.conversation_runner.get_confirmation_policy()

        # Show the confirmation settings modal
        confirmation_modal = ConfirmationSettingsModal(
            current_policy=current_policy,
            on_policy_selected=self._on_confirmation_policy_selected,
        )
        self.push_screen(confirmation_modal)

    def _on_confirmation_policy_selected(self, policy: ConfirmationPolicyBase) -> None:
        """Handle when a confirmation policy is selected from the modal.

        Args:
            policy: The selected confirmation policy
        """
        if not self.conversation_runner:
            return

        # Set the new confirmation policy
        self.conversation_runner.set_confirmation_policy(policy)

        # Show status message based on the policy type
        if isinstance(policy, NeverConfirm):
            policy_name = "Always approve actions (no confirmation)"
        elif isinstance(policy, AlwaysConfirm):
            policy_name = "Confirm every action"
        elif isinstance(policy, ConfirmRisky):
            policy_name = "Confirm high-risk actions only"
        else:
            policy_name = "Custom policy"

        self.notify(f"Confirmation policy set to: {policy_name}")

    def _handle_condense_command(self) -> None:
        """Handle the /condense command to condense conversation history."""
        if not self.conversation_runner:
            self.notify(
                title="Condense Error",
                message="No conversation available to condense",
                severity="error",
            )
            return

        # Use the async condensation method from conversation runner
        # This will handle all error cases and notifications
        asyncio.create_task(self.conversation_runner.condense_async())

    def _handle_feedback_command(self) -> None:
        """Handle the /feedback command to open feedback form in browser."""
        import webbrowser

        feedback_url = "https://forms.gle/chHc5VdS3wty5DwW6"
        webbrowser.open(feedback_url)
        self.notify(
            title="Feedback",
            message="Opening feedback form in your browser...",
            severity="information",
        )

    def _dismiss_pending_feedback_widgets(self) -> None:
        """Remove all pending CriticFeedbackWidget instances from the UI.

        Called when user sends a new message, indicating they chose to
        ignore the feedback prompt.
        """
        from openhands_cli.tui.utils.critic.feedback import CriticFeedbackWidget

        # Find and remove all CriticFeedbackWidget instances
        for widget in self.main_display.query(CriticFeedbackWidget):
            widget.remove()

    def _handle_new_command(self) -> None:
        """Handle the /new command to start a new conversation."""
        self._conversation_manager.create_new()

    def _handle_history_command(self) -> None:
        """Handle the /history command to show conversation history panel."""
        self.action_toggle_history()

    def action_toggle_history(self) -> None:
        """Toggle the history side panel."""
        HistorySidePanel.toggle(
            self,
            current_conversation_id=self.conversation_id,
        )

    @on(ConversationCreated)
    def on_conversation_created(self, event: ConversationCreated) -> None:
        """Propagate conversation creation to history panel."""
        self._notify_history_panel(event)

    @on(ConversationTitleUpdated)
    def on_conversation_title_updated(self, event: ConversationTitleUpdated) -> None:
        """Propagate title update to history panel."""
        self._notify_history_panel(event)

    @on(ConversationSwitched)
    def on_conversation_switched(self, event: ConversationSwitched) -> None:
        """Propagate conversation switch to history panel."""
        self._notify_history_panel(event)

    @on(RevertSelectionRequest)
    def on_revert_selection_request(self, event: RevertSelectionRequest) -> None:
        """Propagate revert selection request to history panel."""
        self._notify_history_panel(event)

    def _notify_history_panel(self, message: Message) -> None:
        """Helper to send message to history panel if it exists.

        This decouples the sender (Manager/Switcher) from the receiver (Panel).
        The sender just posts to App, and App forwards to Panel if present.
        """
        try:
            self.query_one(HistorySidePanel).post_message(message)
        except NoMatches:
            pass

    @on(SwitchConversationRequest)
    def _on_switch_conversation_request(self, event: SwitchConversationRequest) -> None:
        """Handle request from history panel to switch conversations."""
        self._conversation_manager.switch_to(event.conversation_id)

    @on(ConfirmationNeeded)
    def _on_confirmation_needed(self, event: ConfirmationNeeded) -> None:
        """Handle ConfirmationNeeded message - show confirmation panel.

        This is called when the conversation runner needs user confirmation
        for pending actions. The worker has already exited (non-blocking),
        so the UI can safely show the panel and wait for user input.
        """
        # Remove any existing confirmation panel
        if self.confirmation_panel:
            self.confirmation_panel.remove()
            self.confirmation_panel = None

        # Create and mount the inline confirmation panel in main_display
        # This places it underneath the latest action event collapsible
        self.confirmation_panel = InlineConfirmationPanel(
            len(event.pending_actions), self._on_confirmation_decision
        )
        self.main_display.mount(self.confirmation_panel)
        # Scroll to show the confirmation panel
        self.main_display.scroll_end(animate=False)

    def _on_confirmation_decision(self, decision: UserConfirmation) -> None:
        """Handle user's confirmation decision from the panel.

        Posts a ConfirmationProvided message to resume the conversation.
        """
        # Remove the panel
        if self.confirmation_panel:
            self.confirmation_panel.remove()
            self.confirmation_panel = None

        # Post message to resume the conversation
        self.post_message(ConfirmationProvided(decision))

    @on(ConfirmationProvided)
    def _on_confirmation_provided(self, event: ConfirmationProvided) -> None:
        """Handle ConfirmationProvided message - resume conversation.

        Starts a new worker to continue the conversation with the user's decision.
        """
        if not self.conversation_runner:
            return

        # Start a new worker to resume the conversation
        self.run_worker(
            self._resume_conversation_with_decision(event.decision),
            name="resume_conversation",
        )

    async def _resume_conversation_with_decision(
        self, decision: UserConfirmation
    ) -> None:
        """Resume conversation in a background thread with the user's decision."""
        import asyncio

        await asyncio.get_event_loop().run_in_executor(
            None, self._resume_conversation_sync, decision
        )

    def _resume_conversation_sync(self, decision: UserConfirmation) -> None:
        """Synchronously resume conversation with confirmation decision."""
        if not self.conversation_runner:
            return

        self.conversation_runner._update_run_status(True)
        try:
            self.conversation_runner.resume_with_confirmation(decision)
        except Exception as e:
            self.call_from_thread(
                lambda: self.notify(
                    title="Error",
                    message=f"Failed to resume conversation: {e}",
                    severity="error",
                )
            )
        finally:
            self.conversation_runner._update_run_status(False)

    def _handle_exit(self) -> None:
        """Handle exit command with optional confirmation."""
        if self.exit_confirmation:
            self.push_screen(ExitConfirmationModal())
        else:
            self.exit()


def main(
    resume_conversation_id: str | None = None,
    queued_inputs: list[str] | None = None,
    always_approve: bool = False,
    llm_approve: bool = False,
    exit_without_confirmation: bool = False,
    headless: bool = False,
    json_mode: bool = False,
    env_overrides_enabled: bool = False,
    critic_disabled: bool = False,
):
    """Run the textual app.

    Args:
        resume_conversation_id: Optional conversation ID to resume.
        queued_inputs: Optional list of input strings to queue at the start.
        always_approve: If True, auto-approve all actions without confirmation.
        llm_approve: If True, use LLM-based security analyzer (ConfirmRisky policy).
        exit_without_confirmation: If True, exit without showing confirmation dialog.
        headless: If True, run in headless mode (no UI output, auto-approve actions).
        json_mode: If True, enable JSON output mode (implies headless).
        env_overrides_enabled: If True, environment variables will override
            stored LLM settings.
        critic_disabled: If True, critic functionality will be disabled.

    Raises:
        MissingEnvironmentVariablesError: If env_overrides_enabled is True but
            required environment variables are missing. The app exits cleanly and
            the error is re-raised to be handled by the entrypoint.
    """

    # Determine if envs are required to be configured
    # Raise error before textual app is run to avoid traceback
    try:
        SettingsScreen.is_initial_setup_required(
            env_overrides_enabled=env_overrides_enabled
        )
    except MissingEnvironmentVariablesError as e:
        raise e

    # Determine initial confirmation policy from CLI arguments
    # If headless mode is enabled, always use NeverConfirm (auto-approve all actions)
    initial_confirmation_policy = AlwaysConfirm()  # Default
    if headless or always_approve:
        initial_confirmation_policy = NeverConfirm()
    elif llm_approve:
        initial_confirmation_policy = ConfirmRisky(threshold=SecurityRisk.HIGH)

    app = OpenHandsApp(
        exit_confirmation=not exit_without_confirmation,
        resume_conversation_id=uuid.UUID(resume_conversation_id)
        if resume_conversation_id
        else None,
        queued_inputs=queued_inputs,
        initial_confirmation_policy=initial_confirmation_policy,
        headless_mode=headless,
        json_mode=json_mode,
        env_overrides_enabled=env_overrides_enabled,
        critic_disabled=critic_disabled,
    )

    app.run(headless=headless)

    return app.conversation_id


if __name__ == "__main__":
    main()
