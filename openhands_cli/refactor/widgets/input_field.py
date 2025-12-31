from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Container
from textual.content import Content
from textual.events import Paste
from textual.message import Message
from textual.signal import Signal
from textual.widgets import OptionList, TextArea
from textual.widgets.option_list import Option

from openhands_cli.locations import WORK_DIR
from openhands_cli.refactor.core.commands import COMMANDS


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

    class EnterPressed(Message):
        """Message sent when Enter is pressed (for submission)."""

        pass

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

    async def _on_key(self, event) -> None:
        """Intercept Enter key before TextArea processes it."""
        if event.key == "enter":
            # Post message to parent and prevent default newline insertion
            self.post_message(self.EnterPressed())
            event.prevent_default()
            event.stop()
            return
        # Let parent class handle other keys
        await super()._on_key(event)

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


class TextAreaAutoComplete(Container):
    """Custom autocomplete dropdown for AutoGrowTextArea.

    This is a lightweight alternative to textual-autocomplete that works
    with TextArea instead of Input widgets.
    """

    DEFAULT_CSS = """
    TextAreaAutoComplete {
        layer: autocomplete;
        width: auto;
        min-width: 30;
        max-width: 60;
        height: auto;
        max-height: 12;
        display: none;
        background: $surface;
        border: solid $primary;
        padding: 0;
        margin: 0;

        OptionList {
            width: 100%;
            height: auto;
            min-height: 1;
            max-height: 10;
            border: none;
            padding: 0 1;
            margin: 0;
            background: $surface;
        }
    }
    """

    def __init__(
        self,
        target: AutoGrowTextArea,
        command_candidates: list | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.target = target
        self.command_candidates = command_candidates or []
        self._visible = False

    def compose(self):
        """Create the option list for autocomplete."""
        yield OptionList()

    @property
    def option_list(self) -> OptionList:
        """Get the option list widget."""
        return self.query_one(OptionList)

    def show_dropdown(self, candidates: list[Option]) -> None:
        """Show the dropdown with candidates."""
        if not candidates:
            self.hide_dropdown()
            return

        self.option_list.clear_options()
        for candidate in candidates:
            self.option_list.add_option(candidate)

        self._visible = True
        self.display = True
        self.option_list.highlighted = 0

    def hide_dropdown(self) -> None:
        """Hide the dropdown."""
        self._visible = False
        self.display = False

    def is_visible(self) -> bool:
        """Check if dropdown is visible."""
        return self._visible

    def select_highlighted(self) -> str | None:
        """Get the highlighted option value and hide dropdown."""
        if not self._visible:
            return None

        highlighted = self.option_list.highlighted
        if highlighted is not None:
            option = self.option_list.get_option_at_index(highlighted)
            if option:
                self.hide_dropdown()
                prompt = option.prompt
                # Extract text from Rich Text if needed
                if isinstance(prompt, Text):
                    return prompt.plain
                return str(prompt)
        return None

    def move_highlight(self, direction: int) -> None:
        """Move highlight up or down."""
        if not self._visible:
            return

        if direction > 0:
            self.option_list.action_cursor_down()
        else:
            self.option_list.action_cursor_up()

    def get_command_candidates(self, text: str) -> list[Option]:
        """Get command candidates for slash commands."""
        if not text.lstrip().startswith("/"):
            return []

        # If there's a space after the command, don't show autocomplete
        stripped = text.lstrip()
        if " " in stripped:
            return []

        # Filter candidates that match the typed text
        search = stripped.lower()
        candidates = []
        for cmd in self.command_candidates:
            # cmd is a DropdownItem with main (Content or str)
            cmd_main = cmd.main if hasattr(cmd, "main") else cmd
            # Convert Content object to plain string if needed
            cmd_text = (
                str(cmd_main.plain) if hasattr(cmd_main, "plain") else str(cmd_main)
            )
            # Extract just the command part (before " - " if present)
            if " - " in cmd_text:
                cmd_name = cmd_text.split(" - ")[0]
            else:
                cmd_name = cmd_text
            if cmd_name.lower().startswith(search):
                # Use full text for display, command name as id
                candidates.append(Option(cmd_text, id=cmd_name))

        return candidates

    def get_file_candidates(self, text: str) -> list[Option]:
        """Get file path candidates for @ paths."""
        if "@" not in text:
            return []

        # Find the last @ symbol
        at_index = text.rfind("@")
        path_part = text[at_index + 1 :]

        # If there's a space after @, stop completion
        if " " in path_part:
            return []

        # Determine the directory to search
        if "/" in path_part:
            dir_part = "/".join(path_part.split("/")[:-1])
            search_dir = Path(WORK_DIR) / dir_part
            filename_part = path_part.split("/")[-1]
        else:
            search_dir = Path(WORK_DIR)
            filename_part = path_part

        candidates = []
        try:
            if search_dir.exists() and search_dir.is_dir():
                for item in sorted(search_dir.iterdir()):
                    # Skip hidden files unless specifically typing them
                    if item.name.startswith(".") and not filename_part.startswith("."):
                        continue

                    # Match against filename part
                    if not item.name.lower().startswith(filename_part.lower()):
                        continue

                    try:
                        rel_path = item.relative_to(Path(WORK_DIR))
                        path_str = str(rel_path)
                        prefix = "📁 " if item.is_dir() else "📄 "
                        if item.is_dir():
                            path_str += "/"

                        display = f"{prefix}@{path_str}"
                        candidates.append(Option(display, id=f"@{path_str}"))
                    except ValueError:
                        continue
        except (OSError, PermissionError):
            pass

        return candidates

    def update_candidates(self, text: str) -> None:
        """Update candidates based on current input text."""
        candidates = []

        if text.lstrip().startswith("/"):
            candidates = self.get_command_candidates(text)
        elif "@" in text:
            candidates = self.get_file_candidates(text)

        if candidates:
            self.show_dropdown(candidates)
        else:
            self.hide_dropdown()


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
        self.autocomplete = TextAreaAutoComplete(
            self.input_widget, command_candidates=COMMANDS
        )
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

        # Handle autocomplete navigation
        if self.autocomplete.is_visible():
            if event.key == "down":
                self.autocomplete.move_highlight(1)
                event.prevent_default()
                event.stop()
                return
            elif event.key == "up":
                self.autocomplete.move_highlight(-1)
                event.prevent_default()
                event.stop()
                return
            elif event.key == "tab":
                # Tab to select autocomplete option
                selected = self.autocomplete.select_highlighted()
                if selected:
                    self._apply_completion(selected)
                event.prevent_default()
                event.stop()
                return
            elif event.key == "escape":
                self.autocomplete.hide_dropdown()
                event.prevent_default()
                event.stop()
                return

    @on(AutoGrowTextArea.EnterPressed)
    def on_enter_pressed(self, event: AutoGrowTextArea.EnterPressed) -> None:  # noqa: ARG002
        """Handle Enter key press from the input widget."""
        if self.is_multiline_mode:
            return

        # If autocomplete is visible, select and apply completion
        if self.autocomplete.is_visible():
            selected = self.autocomplete.select_highlighted()
            if selected:
                self._apply_completion(selected)
                return

        # Otherwise submit the input
        content = self.input_widget.text.strip()
        if content:
            self.input_widget.clear()
            self.autocomplete.hide_dropdown()
            self.post_message(self.Submitted(content))

    def _apply_completion(self, value: str) -> None:
        """Apply the selected completion to the input."""
        current_text = self.input_widget.text

        if current_text.lstrip().startswith("/"):
            # Command completion - extract just the command
            if " - " in value:
                command_only = value.split(" - ")[0].strip()
            else:
                # Remove any prefix like emoji
                command_only = value.strip()
                if " " in command_only:
                    # Take just the command part (e.g., "/help" from "📁 /help")
                    parts = command_only.split()
                    for part in parts:
                        if part.startswith("/"):
                            command_only = part
                            break

            self.input_widget.text = command_only + " "
            # Move cursor to end
            self.input_widget.move_cursor((0, len(self.input_widget.text)))
        elif "@" in current_text:
            # File completion - replace from last @ to end
            at_index = current_text.rfind("@")
            prefix = current_text[:at_index]
            # Extract the path from value (remove emoji prefix if present)
            path_value = value.strip()
            if " " in path_value:
                parts = path_value.split()
                for part in parts:
                    if part.startswith("@"):
                        path_value = part
                        break

            self.input_widget.text = prefix + path_value + " "
            self.input_widget.move_cursor((0, len(self.input_widget.text)))

    def action_toggle_input_mode(self) -> None:
        """Toggle between single-line Input and multi-line TextArea."""
        # Hide autocomplete when toggling
        self.autocomplete.hide_dropdown()

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
