"""Custom autocomplete functionality for OpenHands CLI.

This module provides enhanced autocomplete behavior for command input,
including suffix-style descriptions and smart completion logic.
"""

from textual_autocomplete import AutoComplete, TargetState


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
