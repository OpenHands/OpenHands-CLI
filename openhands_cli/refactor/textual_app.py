"""Minimal textual app for OpenHands CLI migration.

This is the starting point for migrating from prompt_toolkit to textual.
It creates a basic app with:
- A main container (Static widget) that takes up most of the screen
- An Input widget at the bottom for user messages
- The Input widget is automatically focused
"""

from textual.app import App, ComposeResult
from textual.widgets import Input, Static


class OpenHandsApp(App):
    """A minimal textual app for OpenHands CLI."""

    CSS = """
    #main_container {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }

    #user_input {
        height: 3;
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        # Main container that takes up most of the screen
        content = (
            "OpenHands CLI - Textual Version\n\n"
            "This is the main content area.\n"
            "It will display conversation history and agent responses."
        )
        yield Static(content, id="main_container")

        # Input widget at the bottom for user messages
        yield Input(placeholder="Type your message here...", id="user_input")

    def on_mount(self) -> None:
        """Called when app starts."""
        # Focus the input widget automatically
        self.query_one("#user_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user submits input."""
        user_message = event.value
        if user_message.strip():
            # For now, just display the message in the main container
            main_container = self.query_one("#main_container", Static)
            current_content = str(main_container.content)
            new_content = f"{current_content}\n\n> {user_message}"
            main_container.update(new_content)

            # Clear the input
            event.input.value = ""


def main():
    """Run the textual app."""
    app = OpenHandsApp()
    app.run()


if __name__ == "__main__":
    main()
