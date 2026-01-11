from typing import ClassVar

from textual import on
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.signal import Signal
from textual.widgets import TextArea

from openhands_cli.tui.core.commands import COMMANDS
from openhands_cli.tui.widgets.user_input.single_line_input import (
    SingleLineInputWithWraping,
)
from openhands_cli.tui.widgets.user_input.text_area_with_autocomplete import (
    AutoCompleteDropdown,
)


class InputField(Container):
    """Input field with two modes: auto-growing single-line and multiline.

    Single-line mode (default):
    - Uses SingleLineInputWithWraping
    - Auto-grows height as text wraps (up to max-height)
    - Enter to submit, Shift+Enter/Ctrl+J for newline
    - Full autocomplete support

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

        AutoCompleteDropdown {
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
        self.multiline_mode_status = Signal(self, "multiline_mode_status")
        self.is_multiline = False

    def compose(self):
        """Create the input widgets."""
        self.single_line_widget = SingleLineInputWithWraping(
            placeholder=self.placeholder,
            id="user_input",
        )
        yield self.single_line_widget

        self.multiline_widget = TextArea(
            id="user_textarea",
            soft_wrap=True,
            show_line_numbers=False,
        )
        self.multiline_widget.display = False
        yield self.multiline_widget

        self.autocomplete = AutoCompleteDropdown(command_candidates=COMMANDS)
        yield self.autocomplete

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self._focus_current()

    @property
    def is_multiline_mode(self) -> bool:
        """Check if currently in multiline mode."""
        return self.is_multiline

    def _focus_current(self) -> None:
        """Focus the current mode's widget."""
        if self.is_multiline:
            self.multiline_widget.focus()
        else:
            self.single_line_widget.focus()

    def _get_current_text(self) -> str:
        """Get text from the current mode's widget."""
        if self.is_multiline:
            return self.multiline_widget.text
        return self.single_line_widget.text

    def _set_current_text(self, value: str) -> None:
        """Set text on the current mode's widget."""
        if self.is_multiline:
            self.multiline_widget.text = value
        else:
            self.single_line_widget.text = value

    def _clear_current(self) -> None:
        """Clear the current mode's widget."""
        if self.is_multiline:
            self.multiline_widget.text = ""
        else:
            self.single_line_widget.clear()

    def _move_cursor_to_end(self) -> None:
        """Move cursor to end of current widget."""
        if self.is_multiline:
            self.multiline_widget.move_cursor(self.multiline_widget.document.end)
        else:
            self.single_line_widget.move_cursor(self.single_line_widget.document.end)

    def _activate_single_line(self) -> None:
        """Activate single-line mode."""
        self.multiline_widget.display = False
        self.single_line_widget.display = True
        self.is_multiline = False

    def _activate_multiline(self) -> None:
        """Activate multiline mode."""
        self.autocomplete.hide_dropdown()
        self.single_line_widget.display = False
        self.multiline_widget.display = True
        self.is_multiline = True

    @on(TextArea.Changed)
    def _on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Update autocomplete when text changes in single-line mode."""
        if event.text_area is self.single_line_widget and not self.is_multiline:
            self.autocomplete.update_candidates(self.single_line_widget.text)

    def on_key(self, event) -> None:
        """Handle key events for autocomplete navigation."""
        if self.is_multiline:
            return
        if self.autocomplete.process_key(event.key):
            event.prevent_default()
            event.stop()

    @on(SingleLineInputWithWraping.EnterPressed)
    def _on_enter_pressed(self, event: SingleLineInputWithWraping.EnterPressed) -> None:  # noqa: ARG002
        """Handle Enter key press from the single-line input."""
        if self.is_multiline:
            return

        # Let autocomplete handle enter if visible
        if self.autocomplete.is_visible and self.autocomplete.process_key("enter"):
            return

        self._submit_current_content()

    @on(AutoCompleteDropdown.CompletionSelected)
    def _on_completion_selected(
        self, event: AutoCompleteDropdown.CompletionSelected
    ) -> None:
        """Handle completion selection from autocomplete."""
        self.autocomplete.apply_completion(self.single_line_widget, event.item)

    def action_toggle_input_mode(self) -> None:
        """Toggle between single-line and multiline modes."""
        content = self._get_current_text()

        if self.is_multiline:
            self._activate_single_line()
        else:
            self._activate_multiline()

        self._set_current_text(content)
        self._move_cursor_to_end()
        self._focus_current()

        self.multiline_mode_status.publish(self.is_multiline)

    def action_submit_textarea(self) -> None:
        """Submit content from multiline mode (Ctrl+J)."""
        if self.is_multiline:
            content = self._get_current_text().strip()
            if content:
                self._clear_current()
                self.action_toggle_input_mode()
                self.post_message(self.Submitted(content))

    def _submit_current_content(self) -> None:
        """Submit current content and clear input."""
        content = self._get_current_text().strip()
        if content:
            self._clear_current()
            self.autocomplete.hide_dropdown()
            self.post_message(self.Submitted(content))

    def get_current_value(self) -> str:
        """Get the current input value."""
        return self._get_current_text()

    def focus_input(self) -> None:
        """Focus the current mode's input widget."""
        self._focus_current()

    @on(SingleLineInputWithWraping.PasteDetected)
    def _on_paste_detected(
        self, event: SingleLineInputWithWraping.PasteDetected
    ) -> None:
        """Handle multi-line paste detection - switch to multiline mode."""
        if not self.is_multiline:
            self.single_line_widget.insert(
                event.text,
                self.single_line_widget.cursor_location,
            )
            self.action_toggle_input_mode()
