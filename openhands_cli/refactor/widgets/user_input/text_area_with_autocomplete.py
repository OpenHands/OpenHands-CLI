from pathlib import Path

from rich.text import Text
from textual.containers import Container
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from openhands_cli.locations import WORK_DIR
from openhands_cli.refactor.widgets.user_input.expandable_text_area import (
    AutoGrowTextArea,
)


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
