from typing import ClassVar

from textual import on
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.signal import Signal
from textual.widgets import TextArea

from openhands_cli.tui.core.commands import COMMANDS
from openhands_cli.tui.widgets.user_input.autocomplete_dropdown import (
    AutoCompleteDropdown,
)
from openhands_cli.tui.widgets.user_input.single_line_input import (
    SingleLineInputWithWrapping,
)


class InputField(Container):
    """Input field with two modes: auto-growing single-line and multiline.

    Single-line mode (default):
    - Uses SingleLineInputWithWrapping
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
        self.single_line_widget = SingleLineInputWithWrapping(
            placeholder=self.placeholder,
            id="user_input",
        )
        self.multiline_widget = TextArea(
            id="user_textarea",
            soft_wrap=True,
            show_line_numbers=False,
        )
        self.multiline_widget.display = False
        self.autocomplete = AutoCompleteDropdown(
            single_line_widget=self.single_line_widget, command_candidates=COMMANDS
        )

        self.active_input_widget: SingleLineInputWithWrapping | TextArea = (
            self.single_line_widget
        )

    def compose(self):
        """Create the input widgets."""
        yield self.single_line_widget
        yield self.multiline_widget
        yield self.autocomplete

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.focus_input()

    def focus_input(self) -> None:
        self.active_input_widget.focus()

    @property
    def is_multiline_mode(self) -> bool:
        """Check if currently in multiline mode."""
        return not isinstance(self.active_input_widget, SingleLineInputWithWrapping)

    def _get_current_text(self) -> str:
        """Get text from the current mode's widget."""
        return self.active_input_widget.text

    def _clear_current(self) -> None:
        """Clear the current mode's widget."""
        self.active_input_widget.clear()

    def _activate_single_line(self) -> None:
        """Activate single-line mode."""
        self.multiline_widget.display = False
        self.single_line_widget.display = True
        self.active_input_widget = self.single_line_widget

    def _activate_multiline(self) -> None:
        """Activate multiline mode."""
        self.autocomplete.hide_dropdown()
        self.single_line_widget.display = False
        self.multiline_widget.display = True
        self.active_input_widget = self.multiline_widget

    @on(TextArea.Changed)
    def _on_text_area_changed(self, _event: TextArea.Changed) -> None:
        """Update autocomplete when text changes in single-line mode."""
        if self.is_multiline_mode:
            return

        self.autocomplete.update_candidates()

    def on_key(self, event) -> None:
        """Handle key events for autocomplete navigation."""
        if self.is_multiline_mode:
            return

        if self.autocomplete.process_key(event.key):
            event.prevent_default()
            event.stop()

    @on(SingleLineInputWithWrapping.EnterPressed)
    def _on_enter_pressed(self, event: SingleLineInputWithWrapping.EnterPressed) -> None:  # noqa: ARG002
        """Handle Enter key press from the single-line input."""
        # Let autocomplete handle enter if visible
        if self.autocomplete.is_visible and self.autocomplete.process_key("enter"):
            return

        self._submit_current_content()

    def action_toggle_input_mode(self) -> None:
        """Toggle between single-line and multiline modes."""
        content = self._get_current_text()

        if self.is_multiline_mode:
            self._activate_single_line()
        else:
            self._activate_multiline()

        self.active_input_widget.text = content
        self.active_input_widget.move_cursor(self.active_input_widget.document.end)
        self.focus_input()

        self.multiline_mode_status.publish(self.is_multiline_mode)

    def action_submit_textarea(self) -> None:
        """Submit content from multiline mode (Ctrl+J)."""
        if self.is_multiline_mode:
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
            self.post_message(self.Submitted(content))

    @on(SingleLineInputWithWrapping.MultiLinePasteDetected)
    def _on_paste_detected(
        self, event: SingleLineInputWithWrapping.MultiLinePasteDetected
    ) -> None:
        """Handle multi-line paste detection - switch to multiline mode."""
        if not self.is_multiline_mode:
            self.active_input_widget.insert(
                event.text,
                self.single_line_widget.cursor_location,
            )
            self.action_toggle_input_mode()
