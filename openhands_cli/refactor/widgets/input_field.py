from typing import ClassVar

from textual import on
from textual.binding import Binding
from textual.containers import Container
from textual.content import Content
from textual.events import Paste
from textual.message import Message
from textual.signal import Signal
from textual.widgets import TextArea

from openhands_cli.refactor.core.commands import COMMANDS
from openhands_cli.refactor.widgets.autocomplete import EnhancedAutoComplete


class AutoGrowTextArea(TextArea):
    """A TextArea that auto-grows with content and supports soft wrapping.

    This implementation is based on the toad project's approach:
    - Uses soft_wrap=True for automatic line wrapping at word boundaries
    - Uses compact=True to remove default borders
    - CSS height: auto makes it grow based on content
    - CSS max-height limits maximum growth
    """

    class PasteDetected(Message):
        """Message sent when multi-line paste is detected."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(
        self,
        text: str = "",
        *,
        placeholder: str | Content = "",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            text,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
            soft_wrap=True,  # Enable soft wrapping at word boundaries
            show_line_numbers=False,
            highlight_cursor_line=False,
        )
        # Enable compact mode (removes borders/padding for cleaner look)
        self.compact = True
        self._placeholder = placeholder

    def on_mount(self) -> None:
        """Configure the text area on mount."""
        # Set placeholder after mount
        if self._placeholder:
            self.placeholder = (
                Content(self._placeholder)
                if isinstance(self._placeholder, str)
                else self._placeholder
            )

    @on(Paste)
    async def _on_paste(self, event: Paste) -> None:
        """Handle paste events and detect multi-line content."""
        if "\n" in event.text or "\r" in event.text:
            # Multi-line content detected - notify parent
            self.post_message(self.PasteDetected(event.text))
            event.prevent_default()
            event.stop()
        # For single-line content, let the default paste behavior handle it

    @property
    def value(self) -> str:
        """Compatibility property to match Input widget API."""
        return self.text

    @value.setter
    def value(self, new_value: str) -> None:
        """Set the text content."""
        self.text = new_value

    @property
    def cursor_position(self) -> int:
        """Get cursor position as character offset (for Input API compatibility)."""
        row, col = self.cursor_location
        # Calculate character offset from start
        offset = 0
        lines = self.text.split("\n")
        for i in range(row):
            offset += len(lines[i]) + 1  # +1 for newline
        offset += col
        return offset


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

        #user_input {
            width: 100%;
            height: auto;
            min-height: 3;
            max-height: 8;
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

        yield EnhancedAutoComplete(self.input_widget, command_candidates=COMMANDS)

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.input_widget.focus()

    def on_key(self, event) -> None:
        """Handle key events for submission in single-line mode."""
        if not self.is_multiline_mode and event.key == "enter":
            # In single-line mode, Enter submits
            content = self.input_widget.text.strip()
            if content:
                self.input_widget.clear()
                self.post_message(self.Submitted(content))
                event.prevent_default()
                event.stop()

    def action_toggle_input_mode(self) -> None:
        """Toggle between single-line Input and multi-line TextArea."""
        # Get the input_area container
        input_area = self.screen.query_one("#input_area")

        if self.is_multiline_mode:
            # Switch from TextArea to Input
            # Replace actual newlines with literal "\n" for single-line display
            self.stored_content = self.textarea_widget.text.replace("\n", "\\n")
            self.textarea_widget.display = False
            self.input_widget.display = True
            self.input_widget.value = self.stored_content
            self.input_widget.focus()
            self.is_multiline_mode = False
            # Shrink input area for single-line mode
            input_area.styles.height = 7
        else:
            # Switch from Input to TextArea
            # Replace literal "\n" with actual newlines for multi-line display
            self.stored_content = self.input_widget.value.replace("\\n", "\n")
            self.input_widget.display = False
            self.textarea_widget.display = True
            self.textarea_widget.text = self.stored_content
            self.textarea_widget.focus()
            self.is_multiline_mode = True
            # Expand input area for multi-line mode
            input_area.styles.height = 10

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
            return self.input_widget.value

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
            current_text = self.input_widget.value
            cursor_pos = self.input_widget.cursor_position

            # Insert the pasted text at the cursor position
            new_text = (
                current_text[:cursor_pos] + event.text + current_text[cursor_pos:]
            )

            # Set the combined text in the input widget first
            self.input_widget.value = new_text

            # Then switch to multi-line mode (this will convert the text properly)
            self.action_toggle_input_mode()
