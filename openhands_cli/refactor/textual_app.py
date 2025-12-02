"""Minimal textual app for OpenHands CLI migration.

This is the starting point for migrating from prompt_toolkit to textual.
It creates a basic app with:
- A scrollable main display (RichLog) that shows the splash screen initially
- An Input widget at the bottom for user messages
- A status line showing timer and work directory
- The splash screen content scrolls off as new messages are added
"""

import asyncio
import os
import time
import uuid
from collections.abc import Iterable
from typing import ClassVar

from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Footer, Input, Static, TextArea

from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.risk import SecurityRisk
from openhands_cli.locations import WORK_DIR
from openhands_cli.refactor.autocomplete import EnhancedAutoComplete
from openhands_cli.refactor.commands import COMMANDS, is_valid_command, show_help
from openhands_cli.refactor.confirmation_panel import ConfirmationSidePanel
from openhands_cli.refactor.conversation_runner import ConversationRunner
from openhands_cli.refactor.exit_modal import ExitConfirmationModal
from openhands_cli.refactor.mcp_side_panel import MCPSidePanel
from openhands_cli.refactor.non_clickable_collapsible import NonClickableCollapsible
from openhands_cli.refactor.richlog_visualizer import TextualVisualizer
from openhands_cli.refactor.settings_screen import SettingsScreen
from openhands_cli.refactor.splash import get_splash_content
from openhands_cli.refactor.theme import OPENHANDS_THEME
from openhands_cli.user_actions.types import UserConfirmation


class OpenHandsApp(App):
    """A minimal textual app for OpenHands CLI with scrollable main display."""

    # Key bindings
    BINDINGS: ClassVar = [
        ("f1", "toggle_input_mode", "Toggle single/multi-line input"),
        ("f2", "expand_all", "Expand the cells"),
        ("ctrl+j", "submit_textarea", "Submit multi-line input"),
        ("escape", "pause_conversation", "Pause the conversation"),
        ("ctrl+q", "request_quit", "Quit the application"),
    ]

    def __init__(
        self,
        exit_confirmation: bool = True,
        resume_conversation_id: uuid.UUID | None = None,
        queued_inputs: list[str] | None = None,
        always_approve: bool = False,
        llm_approve: bool = False,
        **kwargs,
    ):
        """Initialize the app with custom OpenHands theme.

        Args:
            exit_confirmation: If True, show confirmation modal before exit.
                             If False, exit immediately.
            resume_conversation_id: Optional conversation ID to resume.
            queued_inputs: Optional list of input strings to queue at the start.
            always_approve: If True, auto-approve all actions without confirmation.
            llm_approve: If True, use LLM-based security analyzer (ConfirmRisky policy).
        """
        super().__init__(**kwargs)

        # Store exit confirmation setting
        self.exit_confirmation = exit_confirmation

        # Store resume conversation ID
        self.conversation_id = (
            resume_conversation_id if resume_conversation_id else uuid.uuid4()
        )

        # Store queued inputs (copy to prevent mutating caller's list)
        self.pending_inputs = list(queued_inputs) if queued_inputs else []

        # Store confirmation policy settings
        self.always_approve = always_approve
        self.llm_approve = llm_approve

        # Initialize conversation runner (updated with write callback in on_mount)
        self.conversation_runner = None

        # Timer tracking
        self.conversation_start_time: float | None = None
        self.timer_update_task: Timer | None = None

        # Confirmation panel tracking
        self.confirmation_panel: ConfirmationSidePanel | None = None

        # MCP panel tracking
        self.mcp_panel: MCPSidePanel | None = None

        # Input mode tracking
        self.is_multiline_mode = False
        self.stored_content = ""

        # Register the custom theme
        self.register_theme(OPENHANDS_THEME)

        # Set the theme as active
        self.theme = "openhands"

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
    }

    #content_area {
        height: 1fr;
        layout: horizontal;
    }

    #main_display {
        height: 1fr;
        margin: 1 1 0 1;
        background: $background;
        color: $foreground;
    }

    #splash_content {
        padding: 1;
        background: $background;
        color: $foreground;
    }

    .user-message {
        padding: 0 1;
        background: $background;
        color: $primary;
    }

    .help-message, .error-message, .status-message {
        padding: 0 1;
        background: $background;
        color: $foreground;
    }

    #input_area {
        height: 9;
        dock: bottom;
        background: $background;
        padding: 1;
        margin-bottom: 1;
    }

    #user_input {
        width: 100%;
        height: 3;
        background: $background;
        color: $foreground;
        border: solid $secondary;
    }

    #user_input:focus {
        border: solid $primary;
        background: $background;
    }

    #user_textarea {
        width: 100%;
        height: 6;
        background: $background;
        color: $foreground;
        border: solid $secondary;
        display: none;
    }

    #user_textarea:focus {
        border: solid $primary;
        background: $background;
    }

    #status_line {
        height: 1;
        background: $background;
        color: $secondary;
        padding: 0 1;
        margin-bottom: 1;
    }

    Footer {
        dock: bottom;
        background: $surface;
        color: $foreground;
    }

    /* Style the cursor to use primary color */
    Input .input--cursor {
        background: $primary;
        color: $background;
    }

    /* Panel-like styling for splash screen elements */
    .splash-banner {
        padding: 0 1;
        background: $background;
        color: $primary;
        text-align: center;
    }

    .splash-version {
        padding: 0 1;
        background: $background;
        color: $foreground;
        text-align: center;
        margin-bottom: 1;
    }

    .status-panel {
        width: auto;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1;
        text-align: center;
        margin: 1 0;
        border-title-align: center;
    }

    .conversation-panel {
        width: auto;
        height: auto;
        border: solid $secondary;
        background: $surface;
        padding: 1;
        text-align: center;
        margin: 1 0;
        border-title-align: center;
    }

    .splash-instruction {
        padding: 0 1;
        background: $background;
        color: $foreground;
        margin: 0;
    }

    .splash-instruction-header {
        padding: 0 1;
        background: $background;
        color: $primary;
        margin: 1 0 0 0;
    }

    .splash-update-notice {
        padding: 0 1;
        background: $background;
        color: $primary;
        margin: 1 0 0 0;
    }
    """

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

        # Input area - docked to bottom
        with Container(id="input_area"):
            text_input = Input(
                placeholder=("Type your message, @mention a file, or / for commands"),
                id="user_input",
            )
            yield text_input

            # TextArea for multi-line input (initially hidden)
            text_area = TextArea(
                id="user_textarea",
                soft_wrap=True,
                show_line_numbers=False,
            )
            yield text_area

            # Add enhanced autocomplete for the input (commands and file paths)
            yield EnhancedAutoComplete(text_input, command_candidates=COMMANDS)

            # Status line - shows work directory and timer (inside input area)
            yield Static(id="status_line")

        # Footer - shows available key bindings
        yield Footer()

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "MCP", "View MCP configurations", self.action_toggle_mcp_panel
        )
        yield SystemCommand(
            "AGENT SETTINGS", "Configure agent settings", self.action_open_settings
        )

    def on_mount(self) -> None:
        """Called when app starts."""
        # Check if user has existing settings
        from openhands_cli.tui.settings.store import AgentStore

        agent_store = AgentStore()
        existing_agent = agent_store.load()

        if existing_agent is None:
            # No existing settings - show settings screen first
            self._show_initial_settings()
            return

        # User has settings - proceed with normal startup
        self._initialize_main_ui()

    def _show_initial_settings(self) -> None:
        """Show settings screen for first-time users."""
        settings_screen = SettingsScreen(is_initial_setup=True)
        self.push_screen(settings_screen, self._handle_initial_settings_result)

    def _handle_initial_settings_result(self, result) -> None:
        """Handle the result from the initial settings screen."""
        if result:
            # Settings were saved successfully - initialize main UI
            self._initialize_main_ui()
            self.notify(
                "Settings saved successfully! Welcome to OpenHands CLI!",
                severity="information",
                timeout=3.0,
            )
        else:
            # Settings were cancelled and no existing settings exist - show exit modal
            self.push_screen(ExitConfirmationModal())

    def _initialize_main_ui(self) -> None:
        """Initialize the main UI components."""
        # Get structured splash content
        splash_content = get_splash_content(
            conversation_id=self.conversation_id.hex, theme=OPENHANDS_THEME
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

        # Get the main display container for the visualizer
        main_display = self.query_one("#main_display", VerticalScroll)

        # Initialize conversation runner with visualizer that can add widgets
        visualizer = TextualVisualizer(main_display, self)

        # Determine initial confirmation policy from CLI arguments
        initial_confirmation_policy = AlwaysConfirm()  # Default
        if self.always_approve:
            initial_confirmation_policy = NeverConfirm()
        elif self.llm_approve:
            initial_confirmation_policy = ConfirmRisky(threshold=SecurityRisk.HIGH)

        self.conversation_runner = ConversationRunner(
            self.conversation_id, visualizer, initial_confirmation_policy
        )

        # Set up confirmation callback
        self.conversation_runner.set_confirmation_callback(
            self._handle_confirmation_request
        )

        # Initialize status line
        self.update_status_line()

        # Focus the input widget
        self.query_one("#user_input", Input).focus()

        # Process any queued inputs
        self._process_queued_inputs()

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
        main_display = self.query_one("#main_display", VerticalScroll)
        user_message_widget = Static(f"> {user_input}", classes="user-message")
        main_display.mount(user_message_widget)
        main_display.scroll_end(animate=False)

        # Handle the message asynchronously
        asyncio.create_task(self._handle_user_message(user_input))

    def get_work_dir_display(self) -> str:
        """Get the work directory display string."""
        work_dir = WORK_DIR

        # Shorten the path for display
        if work_dir.startswith(os.path.expanduser("~")):
            work_dir = work_dir.replace(os.path.expanduser("~"), "~", 1)

        return work_dir

    def update_status_line(self) -> None:
        """Update the status line with current information."""
        status_widget = self.query_one("#status_line", Static)
        work_dir = self.get_work_dir_display()

        # Add input mode indicator
        if self.is_multiline_mode:
            mode_indicator = " [Multi-line: Ctrl+J to submit]"
        else:
            mode_indicator = " [F1 for multi-line]"

        # Only show controls and timer when conversation is running
        if (
            self.conversation_runner
            and self.conversation_runner.is_running
            and self.conversation_start_time
        ):
            elapsed = int(time.time() - self.conversation_start_time)
            status_text = (
                f"{work_dir} ✦ (esc to cancel • {elapsed}s , F2 to show details)"
                f"{mode_indicator}"
            )
        else:
            # Just show work directory when not running
            status_text = f"{work_dir}{mode_indicator}"

        status_widget.update(status_text)

    async def start_timer(self) -> None:
        """Start the conversation timer."""
        self.conversation_start_time = time.time()

        # Cancel any existing timer task
        if self.timer_update_task:
            self.timer_update_task.stop()

        # Start a new timer task that updates every second
        self.timer_update_task = self.set_interval(1.0, self.update_status_line)

    def stop_timer(self) -> None:
        """Stop the conversation timer."""
        if self.timer_update_task:
            self.timer_update_task.stop()
            self.timer_update_task = None

        self.conversation_start_time = None
        self.update_status_line()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user submits input."""
        user_message = event.value.strip()
        if user_message:
            # Add the user message to the main display as a Static widget
            main_display = self.query_one("#main_display", VerticalScroll)
            user_message_widget = Static(f"> {user_message}", classes="user-message")
            main_display.mount(user_message_widget)
            main_display.scroll_end(animate=False)

            # Handle commands - only exact matches
            if is_valid_command(user_message):
                self._handle_command(user_message)
            else:
                # Handle regular messages with conversation runner
                await self._handle_user_message(user_message)

            # Clear the input
            event.input.value = ""

    def _handle_command(self, command: str) -> None:
        """Handle command execution."""
        main_display = self.query_one("#main_display", VerticalScroll)

        if command == "/help":
            show_help(main_display)
        elif command == "/confirm":
            self._handle_confirm_command()
        elif command == "/exit":
            self._handle_exit()
        else:
            error_widget = Static(
                f"Unknown command: {command}", classes="error-message"
            )
            main_display.mount(error_widget)
            main_display.scroll_end(animate=False)

    async def _handle_user_message(self, user_message: str) -> None:
        """Handle regular user messages with the conversation runner."""
        main_display = self.query_one("#main_display", VerticalScroll)

        # Check if conversation runner is initialized
        if self.conversation_runner is None:
            error_widget = Static(
                "[red]Error: Conversation runner not initialized[/red]",
                classes="error-message",
            )
            main_display.mount(error_widget)
            main_display.scroll_end(animate=False)
            return

        # Show that we're processing the message
        if self.conversation_runner.is_running:
            await self.conversation_runner.queue_message(user_message)
            return

        # Start the timer
        self.call_later(self.start_timer)

        # Process message asynchronously to keep UI responsive
        # Only run worker if we have an active app (not in tests)
        try:
            self.run_worker(
                self._process_message_with_timer(user_message),
                name="process_message",
            )
        except RuntimeError:
            # In test environment, just show a placeholder message
            placeholder_widget = Static(
                "[green]Message would be processed by conversation runner[/green]",
                classes="status-message",
            )
            main_display.mount(placeholder_widget)
            main_display.scroll_end(animate=False)

    async def _process_message_with_timer(self, user_message: str) -> None:
        """Process message and handle timer lifecycle."""
        if self.conversation_runner is None:
            return

        try:
            await self.conversation_runner.process_message_async(user_message)
        finally:
            # Stop the timer when processing is complete
            self.stop_timer()

    def action_request_quit(self) -> None:
        """Action to handle Ctrl+Q key binding."""
        self._handle_exit()

    def action_expand_all(self) -> None:
        """Action to handle Ctrl+E key binding - toggle expand/collapse all
        collapsible widgets."""
        main_display = self.query_one("#main_display", VerticalScroll)
        collapsibles = main_display.query(NonClickableCollapsible)

        # Check if any are expanded - if so, collapse all; otherwise expand all
        any_expanded = any(not collapsible.collapsed for collapsible in collapsibles)

        for collapsible in collapsibles:
            collapsible.collapsed = any_expanded

    def action_pause_conversation(self) -> None:
        """Action to handle Esc key binding - pause the running conversation."""
        if self.conversation_runner and self.conversation_runner.is_running:
            # Add a status message immediately to show the pause was triggered
            main_display = self.query_one("#main_display", VerticalScroll)
            pause_widget = Static(
                "[yellow]Pausing conversation...[/yellow]",
                classes="status-message",
            )
            main_display.mount(pause_widget)
            main_display.scroll_end(animate=False)

            # Run the pause operation asynchronously to avoid blocking the UI
            asyncio.create_task(self._pause_conversation_async())

    async def _pause_conversation_async(self) -> None:
        """Pause the conversation asynchronously to avoid blocking the UI."""
        if self.conversation_runner and self.conversation_runner.is_running:
            try:
                # Run the blocking pause operation in a thread pool to avoid blocking
                # the event loop
                await asyncio.to_thread(self.conversation_runner.pause)

                # Update UI to show pause completed
                self._update_pause_status("Conversation paused.")
            except Exception as e:
                # Handle any errors during pause
                self._update_pause_status(f"Failed to pause: {e}")

    def _update_pause_status(self, message: str) -> None:
        """Update the UI with pause status message."""
        main_display = self.query_one("#main_display", VerticalScroll)
        status_widget = Static(
            f"[green]{message}[/green]"
            if "paused" in message.lower()
            else f"[red]{message}[/red]",
            classes="status-message",
        )
        main_display.mount(status_widget)
        main_display.scroll_end(animate=False)

    def _handle_confirm_command(self) -> None:
        """Handle the /confirm command to toggle confirmation mode."""
        if not self.conversation_runner:
            return

        # Toggle confirmation mode
        self.conversation_runner.toggle_confirmation_mode()

        # Show status message
        main_display = self.query_one("#main_display", VerticalScroll)
        mode_status = (
            "enabled"
            if self.conversation_runner.is_confirmation_mode_active
            else "disabled"
        )
        status_widget = Static(
            f"[yellow]Confirmation mode {mode_status}[/yellow]",
            classes="status-message",
        )
        main_display.mount(status_widget)
        main_display.scroll_end(animate=False)

    def _handle_confirmation_request(self, pending_actions: list) -> UserConfirmation:
        """Handle confirmation request by showing the side panel.

        Args:
            pending_actions: List of pending actions that need confirmation

        Returns:
            UserConfirmation decision from the user
        """
        # This will be called from a background thread, so we need to use
        # call_from_thread to interact with the UI safely
        from concurrent.futures import Future

        # Create a future to wait for the user's decision
        decision_future: Future[UserConfirmation] = Future()

        def show_confirmation_panel():
            """Show the confirmation panel in the UI thread."""
            try:
                # Remove any existing confirmation panel
                if self.confirmation_panel:
                    self.confirmation_panel.remove()
                    self.confirmation_panel = None

                # Create callback that will resolve the future
                def on_confirmation_decision(decision: UserConfirmation):
                    # Remove the panel
                    if self.confirmation_panel:
                        self.confirmation_panel.remove()
                        self.confirmation_panel = None
                    # Resolve the future with the decision
                    if not decision_future.done():
                        decision_future.set_result(decision)

                # Create and mount the confirmation panel
                content_area = self.query_one("#content_area", Horizontal)
                self.confirmation_panel = ConfirmationSidePanel(
                    pending_actions, on_confirmation_decision
                )
                content_area.mount(self.confirmation_panel)

            except Exception:
                # If there's an error, default to DEFER
                if not decision_future.done():
                    decision_future.set_result(UserConfirmation.DEFER)

        # Schedule the UI update on the main thread
        self.call_from_thread(show_confirmation_panel)

        # Wait for the user's decision (this will block the background thread)
        try:
            return decision_future.result(timeout=300)  # 5 minute timeout
        except Exception:
            # If timeout or error, default to DEFER
            return UserConfirmation.DEFER

    def _handle_exit(self) -> None:
        """Handle exit command with optional confirmation."""
        if self.exit_confirmation:
            self.push_screen(ExitConfirmationModal())
        else:
            self.exit()

    def action_toggle_mcp_panel(self) -> None:
        """Action to toggle the MCP side panel."""
        content_area = self.query_one("#content_area", Horizontal)

        if self.mcp_panel is None:
            # Create and mount the MCP panel
            agent = None
            try:
                from openhands_cli.tui.settings.store import AgentStore

                agent_store = AgentStore()
                agent = agent_store.load()
            except Exception:
                pass

            self.mcp_panel = MCPSidePanel(agent=agent)
            content_area.mount(self.mcp_panel)
        else:
            # Remove the existing panel
            self.mcp_panel.remove()
            self.mcp_panel = None

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

        # Open the settings screen
        settings_screen = SettingsScreen()
        self.push_screen(settings_screen, self._handle_settings_result)

    def _handle_settings_result(self, result) -> None:
        """Handle the result from the settings screen."""
        if result:
            # Settings were saved successfully - reload the agent
            try:
                from openhands_cli.tui.settings.store import AgentStore

                agent_store = AgentStore()
                self.agent = agent_store.load()

                self.notify(
                    "Settings saved successfully!", severity="information", timeout=3.0
                )
            except Exception as e:
                self.notify(
                    f"Settings saved but failed to reload agent: {str(e)}",
                    severity="warning",
                    timeout=5.0,
                )

    def action_toggle_input_mode(self) -> None:
        """Action to toggle between Input and TextArea."""
        self._toggle_input_mode()

    def action_submit_textarea(self) -> None:
        """Action to handle Ctrl+J key binding - submit TextArea content."""
        if self.is_multiline_mode:
            self._submit_textarea_content()

    def _toggle_input_mode(self) -> None:
        """Toggle between single-line Input and multi-line TextArea."""
        input_widget = self.query_one("#user_input", Input)
        textarea_widget = self.query_one("#user_textarea", TextArea)

        if self.is_multiline_mode:
            # Switch from TextArea to Input
            # Replace actual newlines with literal "\n" for single-line display
            self.stored_content = textarea_widget.text.replace("\n", "\\n")
            textarea_widget.display = False
            input_widget.display = True
            input_widget.value = self.stored_content
            input_widget.focus()
            self.is_multiline_mode = False
        else:
            # Switch from Input to TextArea
            # Replace literal "\n" with actual newlines for multi-line display
            self.stored_content = input_widget.value.replace("\\n", "\n")
            input_widget.display = False
            textarea_widget.display = True
            textarea_widget.text = self.stored_content
            textarea_widget.focus()
            self.is_multiline_mode = True

        # Update status line to reflect the new mode
        self.update_status_line()

    def _submit_textarea_content(self) -> None:
        """Submit the content from the TextArea."""
        textarea_widget = self.query_one("#user_textarea", TextArea)
        content = textarea_widget.text.strip()

        if content:
            # Clear the textarea and switch back to input mode
            textarea_widget.text = ""
            self._toggle_input_mode()

            # Process the content using existing message handling logic
            # Note: content here contains actual newlines, which is what we want
            # for processing multi-line input
            self.run_worker(
                self._handle_textarea_submission(content), name="handle_textarea"
            )

    async def _handle_textarea_submission(self, content: str) -> None:
        """Handle textarea submission using existing message processing logic."""
        # Add the user message to the main display
        main_display = self.query_one("#main_display", VerticalScroll)
        user_message_widget = Static(f"> {content}", classes="user-message")
        main_display.mount(user_message_widget)
        main_display.scroll_end(animate=False)

        # Handle commands - only exact matches
        if is_valid_command(content):
            self._handle_command(content)
        else:
            # Handle regular messages with conversation runner
            await self._handle_user_message(content)


def main(
    resume_conversation_id: str | None = None,
    queued_inputs: list[str] | None = None,
    always_approve: bool = False,
    llm_approve: bool = False,
):
    """Run the textual app.

    Args:
        resume_conversation_id: Optional conversation ID to resume.
        queued_inputs: Optional list of input strings to queue at the start.
        always_approve: If True, auto-approve all actions without confirmation.
        llm_approve: If True, use LLM-based security analyzer (ConfirmRisky policy).
    """
    app = OpenHandsApp(
        resume_conversation_id=uuid.UUID(resume_conversation_id)
        if resume_conversation_id
        else None,
        queued_inputs=queued_inputs,
        always_approve=always_approve,
        llm_approve=llm_approve,
    )
    app.run()

    return app.conversation_id


if __name__ == "__main__":
    main()
