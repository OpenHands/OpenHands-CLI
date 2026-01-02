from pathlib import Path

from textual.containers import Container
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from openhands_cli.locations import WORK_DIR
from openhands_cli.tui.widgets.user_input.models import (
    CompletionItem,
    CompletionType,
)


def detect_completion_type(text: str) -> CompletionType:
    """Detect the type of completion based on input text."""
    stripped = text.lstrip()
    if stripped.startswith("/"):
        # Check if there's a space (command already typed)
        if " " in stripped:
            return CompletionType.NONE
        return CompletionType.COMMAND
    elif "@" in text:
        # Check if there's a space after the last @
        at_index = text.rfind("@")
        path_part = text[at_index + 1 :]
        if " " in path_part:
            return CompletionType.NONE
        return CompletionType.FILE
    return CompletionType.NONE


class TextAreaAutoComplete(Container):
    """Custom autocomplete dropdown for text input.

    This is a lightweight alternative to textual-autocomplete that works
    with TextArea instead of Input widgets. It handles both command (/)
    and file path (@) completions.
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

    class CompletionSelected(Message):
        """Message sent when a completion is selected."""

        def __init__(self, item: CompletionItem) -> None:
            super().__init__()
            self.item = item

    def __init__(
        self,
        command_candidates: list | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.command_candidates = command_candidates or []
        self._current_completion_type = CompletionType.NONE
        self._completion_items: list[CompletionItem] = []

    def compose(self):
        """Create the option list for autocomplete."""
        yield OptionList()

    @property
    def option_list(self) -> OptionList:
        """Get the option list widget."""
        return self.query_one(OptionList)

    @property
    def is_visible(self) -> bool:
        """Check if dropdown is visible."""
        return self.display

    @property
    def current_completion_type(self) -> CompletionType:
        """Get the current completion type being shown."""
        return self._current_completion_type

    def show_dropdown(self, items: list[CompletionItem]) -> None:
        """Show the dropdown with completion items."""
        if not items:
            self.hide_dropdown()
            return

        self._completion_items = items
        self.option_list.clear_options()
        for item in items:
            self.option_list.add_option(
                Option(item.display_text, id=item.completion_value)
            )

        self.display = True
        self.option_list.highlighted = 0

    def hide_dropdown(self) -> None:
        """Hide the dropdown."""
        self.display = False
        self._current_completion_type = CompletionType.NONE
        self._completion_items = []

    def select_highlighted(self) -> CompletionItem | None:
        """Get the highlighted completion item and hide dropdown."""
        if not self.is_visible or not self._completion_items:
            return None

        highlighted = self.option_list.highlighted
        if highlighted is not None and 0 <= highlighted < len(self._completion_items):
            item = self._completion_items[highlighted]
            self.hide_dropdown()
            return item
        return None
    

    def process_key(self, key: str) -> bool:
        """Process keyboard navigation for the autocomplete.

        Returns True if the key was handled, False otherwise.
        """
        if not self.is_visible:
            return False

        if key == "down":
            self.option_list.action_cursor_down()
            return True
        elif key == "up":
            self.option_list.action_cursor_up()
            return True
        elif key == "tab" or key == "enter":
            item = self.select_highlighted()
            if item:
                self.post_message(self.CompletionSelected(item))
                return True
        elif key == "escape":
            self.hide_dropdown()
            return True

        return False

    def _get_command_candidates(self, text: str) -> list[CompletionItem]:
        """Get command candidates for slash commands."""
        stripped = text.lstrip()
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
                candidates.append(
                    CompletionItem(
                        display_text=cmd_text,
                        completion_value=cmd_name,
                        completion_type=CompletionType.COMMAND,
                    )
                )

        return candidates

    def _get_file_candidates(self, text: str) -> list[CompletionItem]:
        """Get file path candidates for @ paths."""
        at_index = text.rfind("@")
        path_part = text[at_index + 1 :]

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
                        candidates.append(
                            CompletionItem(
                                display_text=display,
                                completion_value=f"@{path_str}",
                                completion_type=CompletionType.FILE,
                            )
                        )
                    except ValueError:
                        continue
        except (OSError, PermissionError):
            pass

        return candidates

    def update_candidates(self, text: str) -> None:
        """Update candidates based on current input text."""
        completion_type = detect_completion_type(text)
        self._current_completion_type = completion_type

        candidates: list[CompletionItem] = []
        if completion_type == CompletionType.COMMAND:
            candidates = self._get_command_candidates(text)
        elif completion_type == CompletionType.FILE:
            candidates = self._get_file_candidates(text)

        if candidates:
            self.show_dropdown(candidates)
        else:
            self.hide_dropdown()
