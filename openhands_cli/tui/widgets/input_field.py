import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

from textual import on
from textual.binding import Binding
from textual.containers import Container
from textual.events import Paste
from textual.message import Message
from textual.signal import Signal
from textual.widgets import Input, TextArea

from openhands_cli.tui.core.commands import COMMANDS
from openhands_cli.tui.widgets.autocomplete import EnhancedAutoComplete


class PasteAwareInput(Input):
    """Custom Input widget that can handle paste events and notify parent."""

    class PasteDetected(Message):
        """Message sent when multi-line paste is detected."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    @on(Paste)
    def _on_paste(self, event: Paste) -> None:
        """Handle paste events and detect multi-line content."""
        if "\n" in event.text or "\r" in event.text:
            # Multi-line content detected - notify parent and prevent default
            self.post_message(self.PasteDetected(event.text))
            event.prevent_default()
            event.stop()
        # For single-line content, let the default paste behavior handle it


def get_external_editor() -> str:
    """Get the user's preferred external editor from environment variables.

    Checks VISUAL first, then EDITOR, then falls back to common editors.

    Returns:
        str: The editor command to use

    Raises:
        RuntimeError: If no suitable editor is found
    """
    # Check environment variables in order of preference (VISUAL, then EDITOR)
    for env_var in ["VISUAL", "EDITOR"]:
        editor = os.environ.get(env_var)
        if editor and editor.strip():
            # Handle editors with arguments (e.g., "code --wait")
            editor_parts = editor.split()
            if editor_parts:
                editor_cmd = editor_parts[0]
                if shutil.which(editor_cmd):
                    return editor

    # Fallback to common editors
    for editor in ["nano", "vim", "emacs", "vi"]:
        if shutil.which(editor):
            return editor

    raise RuntimeError(
        "No suitable editor found. Set VISUAL or EDITOR environment variable, "
        "or install nano/vim/emacs."
    )


class InputField(Container):
    BINDINGS: ClassVar = [
        Binding("ctrl+l", "toggle_input_mode", "Toggle single/multi-line input"),
        Binding("ctrl+j", "submit_textarea", "Submit multi-line input"),
        Binding(
            "ctrl+x", "open_external_editor", "Open external editor", priority=True
        ),
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
        self.input_widget = PasteAwareInput(
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

    def action_open_external_editor(self) -> None:
        """Open external editor for composing input."""
        # Debug: notify that the action was triggered
        self.app.notify(
            "CTRL+X triggered - opening external editor...", severity="information"
        )

        try:
            editor_cmd = get_external_editor()
        except RuntimeError as e:
            self.app.notify(str(e), severity="error")
            return

        try:
            # Get current content
            current_content = self.get_current_value()

            # Create temporary file with current content
            with tempfile.NamedTemporaryFile(
                mode="w+", suffix=".txt", delete=False, encoding="utf-8"
            ) as tmp_file:
                tmp_file.write(current_content)
                tmp_path = tmp_file.name

            try:
                # Notify user that editor is opening
                self.app.notify("Opening external editor...", timeout=1)

                # Suspend the TUI and launch editor
                with self.app.suspend():
                    # Split editor command to handle arguments (e.g., "code --wait")
                    editor_args = editor_cmd.split()
                    subprocess.run(editor_args + [tmp_path], check=True)

                # Read the edited content
                with open(tmp_path, encoding="utf-8") as f:
                    edited_content = f.read().rstrip()  # Remove trailing whitespace

                # Only update if content was provided (don't auto-submit)
                if edited_content:
                    self._set_content_only(edited_content)
                    # Show feedback if content changed
                    if edited_content != current_content:
                        self.app.notify(
                            "Content updated from editor", severity="information"
                        )
                else:
                    self.app.notify("Editor closed without content", severity="warning")

            finally:
                # Clean up temporary file
                Path(tmp_path).unlink(missing_ok=True)

        except subprocess.CalledProcessError:
            self.app.notify("Editor was cancelled or failed", severity="warning")
        except Exception as e:
            self.app.notify(f"Editor error: {e}", severity="error")

    def _set_content_only(self, content: str) -> None:
        """Set content in the appropriate widget without submitting."""
        # Check if content has multiple lines
        if "\n" in content:
            # Multi-line content - ensure we're in textarea mode
            if not self.is_multiline_mode:
                self.action_toggle_input_mode()
            self.textarea_widget.text = content
        else:
            # Single-line content - ensure we're in input mode
            if self.is_multiline_mode:
                self.action_toggle_input_mode()
            self.input_widget.value = content

    @on(PasteAwareInput.PasteDetected)
    def on_paste_aware_input_paste_detected(
        self, event: PasteAwareInput.PasteDetected
    ) -> None:
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
