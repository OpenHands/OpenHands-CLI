#!/usr/bin/env python3
"""
Demo script to show the cursor position fix for multi-line paste.

This demonstrates that multi-line content is now inserted at the cursor position
instead of replacing all existing text.
"""

from textual.app import App
from textual.events import Paste
from openhands_cli.refactor.widgets.input_field import InputField


class DemoApp(App):
    """Demo app to test cursor position fix."""

    def compose(self):
        yield InputField(placeholder="Type some text, position cursor, then paste multi-line content")

    def on_mount(self):
        """Set up initial state for demo."""
        input_field = self.query_one(InputField)
        
        # Set some initial text
        initial_text = "Hello World! This is a test."
        input_field.input_widget.value = initial_text
        
        # Position cursor after "Hello " (position 6)
        input_field.input_widget.cursor_position = 6
        
        # Focus the input
        input_field.input_widget.focus()
        
        # Show instructions
        self.title = "Cursor Position Fix Demo"
        self.sub_title = f"Initial text: '{initial_text}' | Cursor at position 6"

    def key_p(self):
        """Press 'p' to simulate pasting multi-line content."""
        input_field = self.query_one(InputField)
        
        # Simulate pasting multi-line content
        paste_text = "Beautiful\nMulti-line\nContent"
        paste_event = Paste(text=paste_text)
        
        # Post the paste event to the input widget
        input_field.input_widget.post_message(paste_event)
        
        # Update subtitle to show what happened
        self.sub_title = "Pressed 'p' to paste multi-line content - should insert at cursor position!"

    def key_r(self):
        """Press 'r' to reset the demo."""
        self.on_mount()

    def key_q(self):
        """Press 'q' to quit."""
        self.exit()


if __name__ == "__main__":
    print("Demo: Multi-line Paste Cursor Position Fix")
    print("==========================================")
    print()
    print("This demo shows that multi-line paste now correctly inserts")
    print("at the cursor position instead of replacing all text.")
    print()
    print("Instructions:")
    print("1. The app starts with 'Hello World! This is a test.'")
    print("2. Cursor is positioned after 'Hello ' (position 6)")
    print("3. Press 'p' to simulate pasting multi-line content")
    print("4. The paste should insert at position 6, creating:")
    print("   'Hello Beautiful\\nMulti-line\\nContentWorld! This is a test.'")
    print("5. Press 'r' to reset, 'q' to quit")
    print()
    print("Expected result: Text inserted at cursor, not replaced!")
    print()
    
    app = DemoApp()
    app.run()