from typing import ClassVar

from textual import on
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.signal import Signal
from textual.widgets import TextArea

from openhands_cli.tui.core.commands import COMMANDS
from openhands_cli.tui.widgets.user_input.multiline_mode import MultilineMode
from openhands_cli.tui.widgets.user_input.single_line_input import (
    SingleLineInputWithWraping,
)
from openhands_cli.tui.widgets.user_input.single_line_mode import SingleLineMode
from openhands_cli.tui.widgets.user_input.text_area_with_autocomplete import (
    TextAreaAutoComplete,
)


class InputField(Container):
    """Input field with two modes: auto-growing single-line and multiline.

    Uses the Strategy pattern to delegate mode-specific behavior to
    SingleLineMode and MultilineMode classes.

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
        self.multiline_mode_status = Signal(self, "multiline_mode_status")
        # For backward compatibility
        self.mutliline_mode_status = self.multiline_mode_status
        # Track if compose() has been called
        self._composed = False

    def compose(self):
        """Create the input widgets and initialize modes."""
        # Create widgets
        self._single_line_widget = SingleLineInputWithWraping(
            placeholder=self.placeholder,
            id="user_input",
        )
        yield self._single_line_widget

        self._multiline_widget = TextArea(
            id="user_textarea",
            soft_wrap=True,
            show_line_numbers=False,
        )
        self._multiline_widget.display = False
        yield self._multiline_widget

        self._autocomplete = TextAreaAutoComplete(command_candidates=COMMANDS)
        yield self._autocomplete

        # Initialize modes
        self._single_line_mode = SingleLineMode(
            self._single_line_widget, self._autocomplete
        )
        self._multiline_mode = MultilineMode(self._multiline_widget)
        self._current_mode = self._single_line_mode
        self._composed = True

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self._current_mode.focus()

    @property
    def is_multiline_mode(self) -> bool:
        """Check if currently in multiline mode."""
        if not self._composed:
            return False
        return self._current_mode is self._multiline_mode

    @on(TextArea.Changed)
    def _on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Update autocomplete when text changes in single-line mode."""
        if event.text_area is self._single_line_widget and not self.is_multiline_mode:
            self._single_line_mode.handle_text_changed()

    def on_key(self, event) -> None:
        """Handle key events for autocomplete navigation."""
        if self.is_multiline_mode:
            return
        if self._single_line_mode.handle_key(event.key):
            event.prevent_default()
            event.stop()

    @on(SingleLineInputWithWraping.EnterPressed)
    def _on_enter_pressed(self, event: SingleLineInputWithWraping.EnterPressed) -> None:  # noqa: ARG002
        """Handle Enter key press from the single-line input."""
        if self.is_multiline_mode:
            return

        # Let autocomplete handle enter if visible
        if self._single_line_mode.handle_enter_for_autocomplete():
            return

        self._submit_current_content()

    @on(TextAreaAutoComplete.CompletionSelected)
    def _on_completion_selected(
        self, event: TextAreaAutoComplete.CompletionSelected
    ) -> None:
        """Handle completion selection from autocomplete."""
        coordinator = self._single_line_mode.get_autocomplete_coordinator()
        coordinator.apply_completion(event.item)

    def action_toggle_input_mode(self) -> None:
        """Toggle between single-line and multiline modes."""
        content = self._current_mode.text
        self._current_mode.on_deactivate()

        if self.is_multiline_mode:
            self._current_mode = self._single_line_mode
        else:
            self._current_mode = self._multiline_mode

        self._current_mode.text = content
        self._current_mode.on_activate()
        self._current_mode.move_cursor_to_end()

        self.multiline_mode_status.publish(self.is_multiline_mode)

    def action_submit_textarea(self) -> None:
        """Submit content from multiline mode (Ctrl+J)."""
        if self.is_multiline_mode:
            content = self._current_mode.text.strip()
            if content:
                self._current_mode.clear()
                self.action_toggle_input_mode()
                self.post_message(self.Submitted(content))

    def _submit_current_content(self) -> None:
        """Submit current content and clear input."""
        content = self._current_mode.text.strip()
        if content:
            self._current_mode.clear()
            coordinator = self._current_mode.get_autocomplete_coordinator()
            if coordinator:
                coordinator.hide()
            self.post_message(self.Submitted(content))

    def get_current_value(self) -> str:
        """Get the current input value."""
        return self._current_mode.text

    def focus_input(self) -> None:
        """Focus the current mode's input widget."""
        self._current_mode.focus()

    @on(SingleLineInputWithWraping.PasteDetected)
    def _on_paste_detected(
        self, event: SingleLineInputWithWraping.PasteDetected
    ) -> None:
        """Handle multi-line paste detection - switch to multiline mode."""
        if not self.is_multiline_mode:
            self._single_line_widget.insert(
                event.text,
                self._single_line_widget.cursor_location,
            )
            self.action_toggle_input_mode()

    # Backward compatibility properties
    @property
    def input_widget(self) -> SingleLineInputWithWraping:
        """Get the single-line input widget (for backward compatibility)."""
        return self._single_line_widget

    @property
    def textarea_widget(self) -> TextArea:
        """Get the multiline textarea widget (for backward compatibility)."""
        return self._multiline_widget

    @property
    def autocomplete(self) -> TextAreaAutoComplete:
        """Get the autocomplete widget (for backward compatibility)."""
        return self._autocomplete
