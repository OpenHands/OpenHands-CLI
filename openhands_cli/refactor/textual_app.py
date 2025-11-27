"""Minimal textual app for OpenHands CLI migration.

This is the starting point for migrating from prompt_toolkit to textual.
It creates a basic app with:
- A scrollable main display (RichLog) that shows the splash screen initially
- An Input widget at the bottom for user messages
- The splash screen content scrolls off as new messages are added
"""

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Collapsible, Input, Static

from openhands_cli.refactor.autocomplete import EnhancedAutoComplete
from openhands_cli.refactor.commands import COMMANDS, is_valid_command
from openhands_cli.refactor.conversation_runner import MinimalConversationRunner
from openhands_cli.refactor.exit_modal import ExitConfirmationModal
from openhands_cli.refactor.richlog_visualizer import TextualVisualizer
from openhands_cli.refactor.splash import get_welcome_message
from openhands_cli.refactor.theme import OPENHANDS_THEME


class OpenHandsApp(App):
    """A minimal textual app for OpenHands CLI with scrollable main display."""

    # Key bindings
    BINDINGS: ClassVar = [
        ("ctrl+q", "request_quit", "Quit"),
        ("ctrl+e", "expand_all", "Toggle All"),
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
        height: 8;
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

    /* Style the cursor to use primary color */
    Input .input--cursor {
        background: $primary;
        color: $background;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        # Main scrollable display - using VerticalScroll to support Collapsible widgets
        with VerticalScroll(id="main_display"):
            # Add initial splash content as a Static widget
            yield Static(id="splash_content")

        # Input area - docked to bottom
        with Container(id="input_area"):
            text_input = Input(
                placeholder=(
                    "Type your message… (tip: press \\ + Enter to insert a newline)"
                ),
                id="user_input",
            )
            yield text_input

            # Add enhanced autocomplete for the input (commands and file paths)
            yield EnhancedAutoComplete(text_input, command_candidates=COMMANDS)

    def on_mount(self) -> None:
        """Called when app starts."""
        # Add the splash screen content to the splash widget
        splash_widget = self.query_one("#splash_content", Static)
        splash_content = get_welcome_message(theme=OPENHANDS_THEME)
        splash_widget.update(splash_content)

        # Get the main display container for the visualizer
        main_display = self.query_one("#main_display", VerticalScroll)

        # Initialize conversation runner with visualizer that can add widgets
        visualizer = TextualVisualizer(main_display, self)

        self.conversation_runner = MinimalConversationRunner(visualizer)

        # Focus the input widget
        self.query_one("#user_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
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
                self._handle_user_message(user_message)

            # Clear the input
            event.input.value = ""

    def _handle_command(self, command: str) -> None:
        """Handle command execution."""
        main_display = self.query_one("#main_display", VerticalScroll)

        if command == "/help":
            # For now, add help as a Static widget - we'll improve this later
            help_widget = Static(
                "Help: Available commands: /help, /exit", classes="help-message"
            )
            main_display.mount(help_widget)
        elif command == "/exit":
            self._handle_exit()
        else:
            error_widget = Static(
                f"Unknown command: {command}", classes="error-message"
            )
            main_display.mount(error_widget)

    def _handle_user_message(self, user_message: str) -> None:
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
            status_widget = Static(
                "[yellow]Agent is already processing a message...[/yellow]",
                classes="status-message",
            )
            main_display.mount(status_widget)
            return

        status_widget = Static(
            "[blue]Processing message...[/blue]", classes="status-message"
        )
        main_display.mount(status_widget)

        # Process message asynchronously to keep UI responsive
        # Only run worker if we have an active app (not in tests)
        try:
            self.run_worker(
                self.conversation_runner.process_message_async(user_message),
                name="process_message",
            )
        except RuntimeError:
            # In test environment, just show a placeholder message
            placeholder_widget = Static(
                "[green]Message would be processed by conversation runner[/green]",
                classes="status-message",
            )
            main_display.mount(placeholder_widget)

    def action_request_quit(self) -> None:
        """Action to handle Ctrl+Q key binding."""
        self._handle_exit()

    def action_expand_all(self) -> None:
        """Action to handle Ctrl+E key binding - toggle expand/collapse all
        collapsible widgets."""
        main_display = self.query_one("#main_display", VerticalScroll)
        collapsibles = main_display.query(Collapsible)

        # Check if any are expanded - if so, collapse all; otherwise expand all
        any_expanded = any(not collapsible.collapsed for collapsible in collapsibles)

        for collapsible in collapsibles:
            collapsible.collapsed = any_expanded

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
