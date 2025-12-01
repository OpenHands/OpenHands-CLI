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
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.timer import Timer
from textual.widgets import Footer, Input, Static

from openhands_cli.locations import WORK_DIR
from openhands_cli.refactor.autocomplete import EnhancedAutoComplete
from openhands_cli.refactor.commands import COMMANDS, is_valid_command, show_help
from openhands_cli.refactor.conversation_runner import MinimalConversationRunner
from openhands_cli.refactor.exit_modal import ExitConfirmationModal
from openhands_cli.refactor.non_clickable_collapsible import NonClickableCollapsible
from openhands_cli.refactor.richlog_visualizer import TextualVisualizer
from openhands_cli.refactor.splash import get_splash_content
from openhands_cli.refactor.theme import OPENHANDS_THEME


class OpenHandsApp(App):
    """A minimal textual app for OpenHands CLI with scrollable main display."""

    # Key bindings
    BINDINGS: ClassVar = [
        ("ctrl+q", "request_quit", "Quit the application"),
        ("f2", "expand_all", "Expand the cells"),
        ("escape", "pause_conversation", "Pause the conversation"),
    ]

    def __init__(self, exit_confirmation: bool = True, **kwargs):
        """Initialize the app with custom OpenHands theme.

        Args:
            exit_confirmation: If True, show confirmation modal before exit.
                             If False, exit immediately.
        """
        super().__init__(**kwargs)

        # Store exit confirmation setting
        self.exit_confirmation = exit_confirmation

        # Initialize conversation runner (updated with write callback in on_mount)
        self.conversation_runner = None

        # Timer tracking
        self.conversation_start_time: float | None = None
        self.timer_update_task: Timer | None = None

        # Register the custom theme
        self.register_theme(OPENHANDS_THEME)

        # Set the theme as active
        self.theme = "openhands"

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
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
        # Main scrollable display - using VerticalScroll to support Collapsible widgets
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

            # Add enhanced autocomplete for the input (commands and file paths)
            yield EnhancedAutoComplete(text_input, command_candidates=COMMANDS)

            # Status line - shows work directory and timer (inside input area)
            yield Static(id="status_line")

        # Footer - shows available key bindings
        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        # Get structured splash content
        splash_content = get_splash_content(theme=OPENHANDS_THEME)

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

        self.conversation_runner = MinimalConversationRunner(visualizer)

        # Initialize status line
        self.update_status_line()

        # Focus the input widget
        self.query_one("#user_input", Input).focus()

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

        # Only show controls and timer when conversation is running
        if (
            self.conversation_runner
            and self.conversation_runner.is_running
            and self.conversation_start_time
        ):
            elapsed = int(time.time() - self.conversation_start_time)
            status_text = (
                f"{work_dir} ✦ (esc to cancel • {elapsed}s , F2 to show details)"
            )
        else:
            # Just show work directory when not running
            status_text = work_dir

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
        elif command == "/exit":
            self._handle_exit()
        else:
            error_widget = Static(
                f"Unknown command: {command}", classes="error-message"
            )
            main_display.mount(error_widget)

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

    def _handle_exit(self) -> None:
        """Handle exit command with optional confirmation."""
        if self.exit_confirmation:
            self.push_screen(ExitConfirmationModal())
        else:
            self.exit()


def main():
    """Run the textual app."""
    app = OpenHandsApp()
    app.run()


if __name__ == "__main__":
    main()
