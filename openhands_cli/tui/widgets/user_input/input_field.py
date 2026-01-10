from typing import ClassVar

from textual import on
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.signal import Signal
from textual.widgets import TextArea

from openhands_cli.tui.core.commands import COMMANDS
from openhands_cli.tui.widgets.user_input.expandable_text_area import (
    AutoGrowTextArea,
)
from openhands_cli.tui.widgets.user_input.models import (
    CompletionItem,
    CompletionType,
)
from openhands_cli.tui.widgets.user_input.text_area_with_autocomplete import (
    TextAreaAutoComplete,
)


class InputField(Container):
    """Input field with two modes: auto-growing single-line and multiline.

    Single-line mode (default):
    - Uses AutoGrowTextArea with soft wrapping
    - Auto-grows height as text wraps (up to max-height)
    - Enter to submit, Shift+Enter/Ctrl+J for newline

    Multiline mode (toggled with Ctrl+L):
    - Uses larger TextArea for explicit multiline editing
    - Ctrl+J to submit
    """

    BINDINGS: ClassVar = [
        Binding("ctrl+l", "toggle_input_mode", "Toggle single/multi-line input"),
        Binding("ctrl+j", "submit_textarea", "Submit multi-line input"),
    ]

    DEFAULT_CSS = """
    InputField {
        width: 100%;
        height: auto;
        min-height: 3;
        layers: base autocomplete;

        #user_input {
            layer: base;
            width: 100%;
            height: auto;
            min-height: 3;
            max-height: 8;
            background: $background;
            color: $foreground;
            border: solid $primary !important;
        }

        #user_input:focus {
            border: solid $primary !important;
            background: $background;
        }

        #user_textarea {
            layer: base;
            width: 100%;
            height: 6;
            background: $background;
            color: $foreground;
            border: solid $primary !important;
            display: none;
        }

        #user_textarea:focus {
            border: solid $primary !important;
            background: $background;
        }

        TextAreaAutoComplete {
            layer: autocomplete;
            offset-x: 1;
            offset-y: -2;
            overlay: screen;
            constrain: inside inflect;
        }
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
        # Auto-growing single-line input (initially visible)
        self.input_widget = AutoGrowTextArea(
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

        # Custom autocomplete for TextArea
        self.autocomplete = TextAreaAutoComplete(command_candidates=COMMANDS)
        yield self.autocomplete

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.input_widget.focus()

    @on(TextArea.Changed)
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Update autocomplete when text changes."""
        if event.text_area is self.input_widget and not self.is_multiline_mode:
            self.autocomplete.update_candidates(self.input_widget.text)

    def on_key(self, event) -> None:
        """Handle key events for autocomplete navigation."""
        if self.is_multiline_mode:
            return

        # Delegate to autocomplete for navigation keys
        if self.autocomplete.process_key(event.key):
            event.prevent_default()
            event.stop()

    @on(AutoGrowTextArea.EnterPressed)
    def on_enter_pressed(self, event: AutoGrowTextArea.EnterPressed) -> None:  # noqa: ARG002
        """Handle Enter key press from the input widget."""
        if self.is_multiline_mode:
            return

        # If autocomplete is visible, let it handle the enter key
        if self.autocomplete.is_visible:
            # handle_key will post CompletionSelected message if successful
            if self.autocomplete.process_key("enter"):
                return

        # Otherwise submit the input
        content = self.input_widget.text.strip()
        if content:
            self.input_widget.clear()
            self.autocomplete.hide_dropdown()
            self.post_message(self.Submitted(content))

    @on(TextAreaAutoComplete.CompletionSelected)
    def on_completion_selected(
        self, event: TextAreaAutoComplete.CompletionSelected
    ) -> None:
        """Handle completion selection from autocomplete."""
        self._apply_completion(event.item)

    def _apply_completion(self, item: CompletionItem) -> None:
        """Apply the selected completion to the input."""
        current_text = self.input_widget.text
        completion_value = item.completion_value

        if item.completion_type == CompletionType.COMMAND:
            # Command completion - replace entire input with command
            self.input_widget.text = completion_value + " "
        elif item.completion_type == CompletionType.FILE:
            # File completion - replace from last @ to end
            at_index = current_text.rfind("@")
            prefix = current_text[:at_index] if at_index >= 0 else ""
            self.input_widget.text = prefix + completion_value + " "

        # Move cursor to end
        self.input_widget.move_cursor((0, len(self.input_widget.text)))

    def action_toggle_input_mode(self) -> None:
        """Toggle between single-line Input and multi-line TextArea."""
        # Hide autocomplete when toggling
        self.autocomplete.hide_dropdown()

        if self.is_multiline_mode:
            # Switch from TextArea to Input
            # Replace actual newlines with literal "\n" for single-line display
            self.stored_content = self.textarea_widget.text
            self.textarea_widget.display = False
            self.input_widget.display = True
            self.input_widget.text = self.stored_content
            self.input_widget.move_cursor(self.input_widget.document.end)
            self.input_widget.focus()
            self.is_multiline_mode = False
        else:
            # Switch from Input to TextArea
            # Replace literal "\n" with actual newlines for multi-line display
            self.stored_content = self.input_widget.text
            self.input_widget.display = False
            self.textarea_widget.display = True
            self.textarea_widget.text = self.stored_content
            # Move cursor to end of text
            self.textarea_widget.move_cursor(self.textarea_widget.document.end)
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

    def get_current_value(self) -> str:
        """Get the current input value."""
        if self.is_multiline_mode:
            return self.textarea_widget.text
        else:
            return self.input_widget.text

    def focus_input(self) -> None:
        """Focus the appropriate input widget."""
        if self.is_multiline_mode:
            self.textarea_widget.focus()
        else:
            self.input_widget.focus()

    @on(AutoGrowTextArea.PasteDetected)
    def on_paste_detected(self, event: AutoGrowTextArea.PasteDetected) -> None:
        """Handle multi-line paste detection from the input widget."""
        # Only handle when in single-line mode
        if not self.is_multiline_mode:
            # Get current text and cursor position before switching modes
            current_text = self.input_widget.text
            self.input_widget.insert(
                event.text, 
                self.input_widget.cursor_location,
            )
            # Switch to multi-line mode
            self.action_toggle_input_mode()
