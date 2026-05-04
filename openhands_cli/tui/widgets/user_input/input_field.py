import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.reactive import reactive
from textual.signal import Signal
from textual.widgets import TextArea

from openhands_cli.stores.prompt_history import PromptHistoryStore
from openhands_cli.tui.core.commands import COMMANDS, is_valid_command
from openhands_cli.tui.messages import SendMessage, SlashCommandSubmitted
from openhands_cli.tui.modals.history_search import HistorySearchScreen
from openhands_cli.tui.widgets.user_input.autocomplete_dropdown import (
    AutoCompleteDropdown,
)
from openhands_cli.tui.widgets.user_input.single_line_input import (
    SingleLineInputWithWrapping,
)


class MultilineInput(TextArea):
    """A multiline TextArea with ctrl+a bound to select all."""

    BINDINGS: ClassVar = [
        # Override default ctrl+a (cursor_line_start) to select all instead
        Binding("ctrl+a", "select_all", "Select all", show=True),
    ]


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
    """Input field with two modes: auto-growing single-line and multiline.

    Single-line mode (default):
    - Uses SingleLineInputWithWrapping
    - Auto-grows height as text wraps (up to max-height)
    - Enter to submit, Shift+Enter/Ctrl+J for newline
    - Full autocomplete support

    Multiline mode (toggled with Ctrl+L):
    - Uses larger TextArea for explicit multiline editing
    - Ctrl+J to submit

    Reactive Behavior:
    - Binds to `conversation_id` from ConversationContainer
    - Auto-disables during conversation switches
    """

    BINDINGS: ClassVar = [
        Binding("ctrl+l", "toggle_input_mode", "Toggle single/multi-line input"),
        Binding("ctrl+j", "submit_textarea", "Submit multi-line input"),
        Binding(
            "ctrl+x", "open_external_editor", "Open external editor", priority=True
        ),
        Binding("ctrl+r", "search_history", "Search prompt history"),
    ]

    # Reactive properties bound from ConversationContainer
    # None = switching in progress (input disabled)
    conversation_id: reactive[uuid.UUID | None] = reactive(None)
    # >0 = waiting for user confirmation (input disabled)
    pending_action_count: reactive[int] = reactive(0)

    DEFAULT_CSS = """
    InputField {
        width: 100%;
        height: auto;
        min-height: 3;

        #single_line_input {
            width: 100%;
            height: auto;
            min-height: 3;
            max-height: 8;
            background: $background;
            color: $foreground;
            border: round $primary !important;
        }

        #single_line_input:focus {
            border: round $primary !important;
            background: $background;
        }

        #multiline_input {
            width: 100%;
            height: 6;
            background: $background;
            color: $foreground;
            border: round $primary;
            display: none;
        }

        #multiline_input:focus {
            border: round $primary;
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
        self.multiline_mode_status = Signal(self, "multiline_mode_status")
        self.single_line_widget = SingleLineInputWithWrapping(
            placeholder=self.placeholder,
            id="single_line_input",
        )
        self.multiline_widget = MultilineInput(
            id="multiline_input",
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

        # Prompt history state
        self.history_store = PromptHistoryStore()
        self.history_index: int = -1  # -1 means not navigating history
        self._history_cache: list[str] = []
        self._input_before_history: str = ""

    def compose(self) -> ComposeResult:
        """Create the input widgets."""
        yield self.autocomplete
        yield self.single_line_widget
        yield self.multiline_widget

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.focus_input()

    def watch_conversation_id(self, conversation_id: uuid.UUID | None) -> None:
        """React to conversation_id changes - disable input when None (switching)."""
        self._update_disabled_state()
        if conversation_id is not None and self.pending_action_count == 0:
            # Re-enable and focus when switch completes
            self.focus_input()

    def watch_pending_action_count(self, count: int) -> None:
        """React to pending_action_count changes - disable input when >0."""
        self._update_disabled_state()
        if count == 0 and self.conversation_id is not None:
            # Re-enable and focus when confirmation is complete
            self.focus_input()

    def _update_disabled_state(self) -> None:
        """Update disabled state based on conversation_id and pending actions."""
        is_switching = self.conversation_id is None
        is_waiting = self.pending_action_count > 0
        self.disabled = is_switching or is_waiting

    def focus_input(self) -> None:
        self.active_input_widget.focus()

    def action_search_history(self) -> None:
        """Open the history search modal."""

        def handle_search_result(selected_text: str | None) -> None:
            if selected_text:
                # If current input is empty or we're replacing, update text
                # We also auto-toggle to multiline mode if selected text is multiline
                if "\n" in selected_text and not self.is_multiline_mode:
                    self.action_toggle_input_mode()

                self.active_input_widget.text = selected_text
                self.active_input_widget.move_cursor(
                    self.active_input_widget.document.end
                )

                # Sync history index so Up/Down arrows work contextually
                self._history_cache = self.history_store.load()
                try:
                    self.history_index = self._history_cache.index(selected_text)
                    self._input_before_history = (
                        ""  # Clear WIP as we are now "in" history
                    )
                except ValueError:
                    # If for some reason it's not in cache, reset to bottom
                    self.history_index = -1

                self.focus_input()

        self.app.push_screen(HistorySearchScreen(), handle_search_result)

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
            current_content = self._get_current_text()

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
                    self.active_input_widget.text = edited_content
                    self.active_input_widget.move_cursor(
                        self.active_input_widget.document.end
                    )
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

    @on(TextArea.Changed)
    def _on_text_area_changed(self, _event: TextArea.Changed) -> None:
        """Update autocomplete when text changes in single-line mode."""
        if self.is_multiline_mode:
            return

        self.autocomplete.update_candidates()

    def on_key(self, event: events.Key) -> None:
        """Handle key events for autocomplete and history navigation."""
        # Autocomplete takes priority (only in single-line mode)
        if not self.is_multiline_mode and self.autocomplete.process_key(event.key):
            event.prevent_default()
            event.stop()
            return

        # History navigation (Arrows)
        if event.key in ("up", "down"):
            if self._handle_history_navigation(event.key):
                event.prevent_default()
                event.stop()

    def _handle_history_navigation(self, direction: str) -> bool:
        """Handle up/down arrow for prompt history navigation.

        Returns:
            bool: True if navigation happened and event should be stopped.
        """
        # Autocomplete check
        if not self.is_multiline_mode and self.autocomplete.is_visible:
            return False

        # In multiline mode, only navigate if cursor is at the boundary
        if self.is_multiline_mode:
            cursor_line, _ = self.active_input_widget.cursor_location
            if direction == "up" and cursor_line > 0:
                return False
            if direction == "down":
                last_line = self.active_input_widget.document.line_count - 1
                if cursor_line < last_line:
                    return False

        # Load history on first 'up'
        if not self._history_cache:
            self._history_cache = self.history_store.load()
            if not self._history_cache:
                return False

        if direction == "up":
            # If starting navigation, save current input
            if self.history_index == -1:
                self._input_before_history = self._get_current_text()

            if self.history_index < len(self._history_cache) - 1:
                self.history_index += 1
                self._apply_history_item(direction)
                return True

        elif direction == "down":
            if self.history_index > -1:
                self.history_index -= 1
                if self.history_index == -1:
                    # Restore what was there before navigation
                    self._restore_original_input()
                else:
                    self._apply_history_item(direction)
                return True

        return False

    def _apply_history_item(self, direction: str) -> None:
        """Apply the current history item and adjust input mode if needed."""
        if 0 <= self.history_index < len(self._history_cache):
            text = self._history_cache[self.history_index]
            is_item_multiline = "\n" in text

            # Sync mode if necessary
            if is_item_multiline != self.is_multiline_mode:
                self.action_toggle_input_mode()

            self.active_input_widget.text = text

            # Place cursor contextually:
            # If moving UP, go to the START of the prompt (to allow continued scrolling)
            # If moving DOWN, go to the END of the prompt
            if direction == "up":
                self.active_input_widget.move_cursor((0, 0))
            else:
                self.active_input_widget.move_cursor(
                    self.active_input_widget.document.end
                )

    def _restore_original_input(self) -> None:
        """Restore the input that was there before history navigation started."""
        text = self._input_before_history
        is_text_multiline = "\n" in text

        if is_text_multiline != self.is_multiline_mode:
            self.action_toggle_input_mode()

        self.active_input_widget.text = text
        self.active_input_widget.move_cursor(self.active_input_widget.document.end)

    @on(SingleLineInputWithWrapping.EnterPressed)
    def _on_enter_pressed(
        self,
        event: SingleLineInputWithWrapping.EnterPressed,  # noqa: ARG002
    ) -> None:
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
                # Store the content before clearing/toggling
                self._submit_current_content()
                # If we're still in multiline mode, toggle back to single line
                if self.is_multiline_mode:
                    self.action_toggle_input_mode()

    def _submit_current_content(self) -> None:
        """Submit current content and clear input.

        Posts different messages based on content type:
        - SlashCommandSubmitted for valid slash commands
        - SendMessage for regular user input
        """
        content = self._get_current_text().strip()
        if not content:
            return

        self._clear_current()
        self.history_index = -1
        self._history_cache = []

        # Save to history before processing
        self.history_store.append(content)

        # Check if this is a valid slash command
        if is_valid_command(content):
            # Extract command name (without the leading slash)
            command = content[1:]  # Remove leading "/"
            self.post_message(SlashCommandSubmitted(command=command))
        else:
            # Regular user input
            self.post_message(SendMessage(content=content))

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
