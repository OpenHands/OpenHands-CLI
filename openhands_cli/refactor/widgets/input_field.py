from typing import ClassVar

from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.signal import Signal
from textual.widgets import Input, TextArea

from openhands_cli.refactor.core.commands import COMMANDS
from openhands_cli.refactor.widgets.autocomplete import EnhancedAutoComplete


class InputField(Container):
    BINDINGS: ClassVar = [
        Binding("ctrl+l", "toggle_input_mode", "Toggle single/multi-line input"),
        Binding("ctrl+j", "submit_textarea", "Submit multi-line input"),
    ]

    DEFAULT_CSS = """
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

    /* Style the cursor to use primary color */
    Input .input--cursor {
        background: $primary;
        color: $background;
    }
    """

    class Submitted(Message):
        """Message sent when input is submitted."""

        def __init__(self, content: str) -> None:
            super().__init__()
            self.content = content

    def __init__(self, placeholder: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.placeholder = placeholder
        self.is_multiline_mode = False
        self.stored_content = ""
        self.mutliline_mode_status = Signal(self, "mutliline_mode_status")

    def compose(self):
        """Create the input widgets."""
        # Single-line input (initially visible)
        self.input_widget = Input(
            placeholder=self.placeholder,
            id="user_input",
        )
        yield self.input_widget

        # Multi-line textarea (initially hidden)
        self.textarea_widget = TextArea(
            id="user_textarea",
            soft_wrap=True,
            show_line_numbers=False,
        )
        self.textarea_widget.display = False
        yield self.textarea_widget

        yield EnhancedAutoComplete(self.input_widget, command_candidates=COMMANDS)

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.input_widget.focus()

    def action_toggle_input_mode(self) -> None:
        """Toggle between single-line Input and multi-line TextArea."""
        if self.is_multiline_mode:
            # Switch from TextArea to Input
            # Replace actual newlines with literal "\n" for single-line display
            self.stored_content = self.textarea_widget.text.replace("\n", "\\n")
            self.textarea_widget.display = False
            self.input_widget.display = True
            self.input_widget.value = self.stored_content
            self.input_widget.focus()
            self.is_multiline_mode = False
        else:
            # Switch from Input to TextArea
            # Replace literal "\n" with actual newlines for multi-line display
            self.stored_content = self.input_widget.value.replace("\\n", "\n")
            self.input_widget.display = False
            self.textarea_widget.display = True
            self.textarea_widget.text = self.stored_content
            self.textarea_widget.focus()
            self.is_multiline_mode = True

        self.mutliline_mode_status.publish(self.is_multiline_mode)

    def action_submit_textarea(self) -> None:
        """Submit the content from the TextArea."""
        if self.is_multiline_mode:
            content = self.textarea_widget.text.strip()
            if content:
                # Clear the textarea and switch back to input mode
                self.textarea_widget.text = ""
                self.action_toggle_input_mode()
                # Submit the content
                self.post_message(self.Submitted(content))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle single-line input submission."""
        if not self.is_multiline_mode:
            content = event.value.strip()
            if content:
                # Clear the input
                self.input_widget.value = ""
                # Submit the content
                self.post_message(self.Submitted(content))

    def get_current_value(self) -> str:
        """Get the current input value."""
        if self.is_multiline_mode:
            return self.textarea_widget.text
        else:
            return self.input_widget.value

    def focus_input(self) -> None:
        """Focus the appropriate input widget."""
        if self.is_multiline_mode:
            self.textarea_widget.focus()
        else:
            self.input_widget.focus()
