"""Minimal textual app for OpenHands CLI migration.

This is the starting point for migrating from prompt_toolkit to textual.
It creates a basic app with:
- A scrollable main display (RichLog) that shows the splash screen initially
- An Input widget at the bottom for user messages
- The splash screen content scrolls off as new messages are added
"""

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.theme import Theme
from textual.widgets import Input, RichLog

from openhands_cli.refactor.splash import get_welcome_message


class OpenHandsApp(App):
    """A minimal textual app for OpenHands CLI with scrollable main display."""

    def __init__(self, **kwargs):
        """Initialize the app with custom OpenHands theme."""
        super().__init__(**kwargs)

        # Create custom OpenHands theme
        self.openhands_theme = Theme(
            name="openhands",
            primary="#ffe165",  # Logo, cursor color
            secondary="#ffffff",  # Borders, plain text
            accent="#277dff",  # Special text like "initialize conversation"
            foreground="#ffffff",  # Default text color
            background="#222222",  # Background color
            surface="#222222",  # Surface color (same as background)
            panel="#222222",  # Panel color (same as background)
            success="#fae279",  # Success messages (use logo color)
            warning="#fae279",  # Warning messages (use logo color)
            error="#fae279",  # Error messages (use logo color)
            dark=True,  # This is a dark theme
            variables={
                # Placeholder text color
                "input-placeholder-foreground": "#727987",
                # Cursor color
                "input-cursor-foreground": "#ffe165",
                # Selection colors
                "input-selection-background": "#fae279 20%",
            },
        )

        # Register the custom theme
        self.register_theme(self.openhands_theme)

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

    def on_mount(self) -> None:
        """Called when app starts."""
        # Add the splash screen content to the main display
        main_display = self.query_one("#main_display", RichLog)
        splash_content = get_welcome_message()
        main_display.write(splash_content)

        # Focus the input widget
        self.query_one("#user_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user submits input."""
        user_message = event.value
        if user_message.strip():
            # Add the user message to the main display
            main_display = self.query_one("#main_display", RichLog)
            main_display.write(f"\n> {user_message}")

            # Clear the input
            event.input.value = ""


def main():
    """Run the textual app."""
    app = OpenHandsApp()
    app.run()


if __name__ == "__main__":
    main()
