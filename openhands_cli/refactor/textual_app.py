"""Minimal textual app for OpenHands CLI migration.

This is the starting point for migrating from prompt_toolkit to textual.
It creates a basic app with:
- A scrollable main display (RichLog) that shows the splash screen initially
- An Input widget at the bottom for user messages
- The splash screen content scrolls off as new messages are added
"""

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Input, RichLog

from openhands_cli.refactor.autocomplete import EnhancedAutoComplete
from openhands_cli.refactor.commands import COMMANDS, is_valid_command, show_help
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
        overflow-y: scroll;
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
        # Main scrollable display
        main_display = RichLog(id="main_display", highlight=False, markup=True)
        main_display.can_focus = False
        yield main_display

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
        # Add the splash screen content to the main display
        main_display = self.query_one("#main_display", RichLog)
        splash_content = get_welcome_message(theme=OPENHANDS_THEME)
        main_display.write(splash_content)

        # Initialize conversation runner with write callback to main display
        visualizer = TextualVisualizer(main_display, self)

        self.conversation_runner = MinimalConversationRunner(visualizer)

        # Focus the input widget
        self.query_one("#user_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user submits input."""
        user_message = event.value.strip()
        if user_message:
            # Add the user message to the main display
            main_display = self.query_one("#main_display", RichLog)
            main_display.write(f"\n> {user_message}")

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
        main_display = self.query_one("#main_display", RichLog)

        if command == "/help":
            show_help(main_display)
        elif command == "/exit":
            self._handle_exit()
        else:
            main_display.write(f"Unknown command: {command}")

    def _handle_user_message(self, user_message: str) -> None:
        """Handle regular user messages with the conversation runner."""
        main_display = self.query_one("#main_display", RichLog)

        # Check if conversation runner is initialized
        if self.conversation_runner is None:
            main_display.write("[red]Error: Conversation runner not initialized[/red]")
            return

        # Show that we're processing the message
        if self.conversation_runner.is_running:
            main_display.write(
                "[yellow]Agent is already processing a message...[/yellow]"
            )
            return

        main_display.write("[blue]Processing message...[/blue]")

        # Process message asynchronously to keep UI responsive
        # Only run worker if we have an active app (not in tests)
        try:
            self.run_worker(
                self.conversation_runner.process_message_async(user_message),
                name="process_message",
            )
        except RuntimeError:
            # In test environment, just show a placeholder message
            main_display.write(
                "[green]Message would be processed by conversation runner[/green]"
            )

    def action_request_quit(self) -> None:
        """Action to handle Ctrl+Q key binding."""
        self._handle_exit()

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
