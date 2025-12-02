"""Custom autocomplete functionality for OpenHands CLI.

This module provides enhanced autocomplete behavior for command input,
including suffix-style descriptions and smart completion logic.
"""

from pathlib import Path

from rich.text import Text
from textual_autocomplete import AutoComplete, DropdownItem, TargetState

from openhands_cli.locations import WORK_DIR


class CommandAutoComplete(AutoComplete):
    """Custom AutoComplete showing descriptions after commands, completing command."""

    def get_search_string(self, target_state: TargetState) -> str:
        """Only match on the leading command token (e.g. `/help`).

        Any characters after the first space (like arguments or ` - `)
        will stop autocomplete from matching at all.
        """
        # Text up to the cursor
        raw = target_state.text[: target_state.cursor_position]

        # Ignore leading whitespace
        raw = raw.lstrip()

        # Only trigger autocomplete if we're starting with a slash-command
        if not raw.startswith("/"):
            return ""

        # If there's a space, user has started typing arguments (" /help - ...")
        # => stop matching entirely
        if " " in raw:
            return ""

        # Otherwise, use the whole token as the search string (e.g. "/he", "/help")
        return raw

    def apply_completion(self, value: str, state) -> None:  # noqa: ARG002
        """Apply completion, but only insert the command part (before the ' - ')."""
        # Extract just the command part (before the description)
        if " - " in value:
            command_only = value.split(" - ")[0]
        else:
            command_only = value

        # Apply the command-only completion to the target input
        if self.target:
            self.target.value = ""
            self.target.insert_text_at_cursor(command_only)


class EnhancedAutoComplete(AutoComplete):
    """Enhanced AutoComplete that handles both commands (/) and file paths (@)."""

    def __init__(self, target, command_candidates=None, **kwargs):
        """Initialize with command candidates and no static candidates."""
        self.command_candidates = command_candidates or []
        # Don't pass candidates to parent - we'll handle them dynamically
        super().__init__(target, candidates=None, **kwargs)

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        """Get candidates based on the current input context."""
        # Text up to the cursor
        raw = target_state.text[: target_state.cursor_position]

        # Check if we're at the start of the input for command completion
        if raw.lstrip().startswith("/"):
            # Command completion (only at start of input)
            return self._get_command_candidates(raw.lstrip())
        elif "@" in raw:
            # File path completion (anywhere in the input)
            return self._get_file_candidates(raw)
        else:
            # No completion for other cases
            return []

    def _get_command_candidates(self, raw: str) -> list[DropdownItem]:
        """Get command candidates for slash commands."""
        # If there's a space, user has started typing arguments
        if " " in raw:
            return []

        return self.command_candidates

    def _get_file_candidates(self, raw: str) -> list[DropdownItem]:
        """Get file path candidates for @ paths."""
        # Find the last @ symbol in the text
        at_index = raw.rfind("@")
        if at_index == -1:
            return []

        # Extract the path part after the @
        path_part = raw[at_index + 1 :]  # Remove @ and everything before it

        # If there's a space, stop completion
        if " " in path_part:
            return []

        # Determine the directory to search in
        if "/" in path_part:
            # User is typing a path with directories
            dir_part = "/".join(path_part.split("/")[:-1])
            search_dir = Path(WORK_DIR) / dir_part
            filename_part = path_part.split("/")[-1]
        else:
            # User is typing in the root working directory
            search_dir = Path(WORK_DIR)
            filename_part = path_part

        candidates = []

        try:
            if search_dir.exists() and search_dir.is_dir():
                # Get all files and directories
                for item in sorted(search_dir.iterdir()):
                    # Skip hidden files unless user is specifically typing them
                    if item.name.startswith(".") and not filename_part.startswith("."):
                        continue

                    # Create relative path from working directory
                    try:
                        rel_path = item.relative_to(Path(WORK_DIR))
                        path_str = str(rel_path)

                        # Add trailing slash for directories
                        if item.is_dir():
                            path_str += "/"
                            prefix = "📁"
                        else:
                            prefix = "📄"

                        candidates.append(
                            DropdownItem(main=f"@{path_str}", prefix=prefix)
                        )
                    except ValueError:
                        # Item is not relative to WORK_DIR, skip it
                        continue

        except (OSError, PermissionError):
            # Directory doesn't exist or no permission
            pass

        return candidates

    def get_search_string(self, target_state: TargetState) -> str:
        """Get the search string based on the input type."""
        raw = target_state.text[: target_state.cursor_position]

        # Check if we're at the start of the input for command completion
        if raw.lstrip().startswith("/"):
            # Command completion - only match if no spaces
            stripped = raw.lstrip()
            if " " in stripped:
                return ""
            return stripped
        elif "@" in raw:
            # File path completion - match the path part after the last @
            at_index = raw.rfind("@")
            if at_index == -1:
                return ""

            path_part = raw[at_index + 1 :]
            if " " in path_part:
                return ""
            # Return the filename part for matching
            if "/" in path_part:
                return path_part.split("/")[-1]
            else:
                return path_part
        else:
            return ""

    def should_show_dropdown(self, search_string: str) -> bool:
        """Override to show dropdown even with empty search string for @ and /."""
        option_list = self.option_list
        option_count = option_list.option_count

        # If no options, don't show dropdown
        if option_count == 0:
            return False

        # For our enhanced autocomplete, show dropdown even with empty search string
        # This allows immediate display when typing @ or completing folders with /
        if option_count == 1:
            first_option = option_list.get_option_at_index(0).prompt
            text_from_option = (
                first_option.plain if isinstance(first_option, Text) else first_option
            )
            # Don't show if the single option exactly matches what's already typed
            return text_from_option != search_string
        else:
            # Show dropdown if we have multiple options, regardless of search string
            return True

    def apply_completion(self, value: str, state) -> None:  # noqa: ARG002
        """Apply completion based on the type of completion."""
        if self.target is None:
            return

        current_text = self.target.value

        if current_text.lstrip().startswith("/"):
            # Command completion - extract just the command part
            if " - " in value:
                command_only = value.split(" - ")[0]
            else:
                command_only = value
            self.target.value = ""
            self.target.insert_text_at_cursor(command_only)
        elif "@" in current_text:
            # File path completion - replace from the last @ to the end
            at_index = current_text.rfind("@")
            if at_index != -1:
                # Keep everything before the @ and replace with the new value
                prefix = current_text[:at_index]
                self.target.value = ""
                self.target.insert_text_at_cursor(prefix + value)
