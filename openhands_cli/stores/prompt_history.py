"""Storage and management of user prompt history."""

import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from openhands_cli.locations import get_prompt_history_path


class PromptHistoryEntry(TypedDict):
    """A single entry in the prompt history."""

    text: str
    timestamp: str


class PromptHistoryStore:
    """Manages persistence of user prompt history for a project.

    Stored as a JSON list of entries in the project's directory.
    """

    def __init__(self, max_entries: int = 100) -> None:
        self.path = Path(get_prompt_history_path())
        self.max_entries = max_entries

    def load_entries(self) -> list[PromptHistoryEntry]:
        """Load prompt history entries, newest first."""
        if not self.path.exists():
            return []

        try:
            with open(self.path, encoding="utf-8") as f:
                entries: list[PromptHistoryEntry] = json.load(f)

            if not isinstance(entries, list):
                return []

            # Reverse so that index 0 is the most recent
            return list(reversed(entries))

        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            return []

    def load(self) -> list[str]:
        """Load prompt history strings, newest first."""
        return [e["text"] for e in self.load_entries()]

    def append(self, text: str) -> None:
        """Append a new prompt to history."""
        text = text.strip()
        if not text:
            return

        entries: list[PromptHistoryEntry] = []
        if self.path.exists():
            try:
                with open(self.path, encoding="utf-8") as f:
                    entries = json.load(f)
                if not isinstance(entries, list):
                    entries = []
            except (json.JSONDecodeError, OSError):
                entries = []

        # Don't add if it's identical to the last entry
        if entries and entries[-1].get("text") == text:
            return

        new_entry: PromptHistoryEntry = {
            "text": text,
            "timestamp": datetime.now().isoformat(),
        }
        entries.append(new_entry)

        # Truncate if too many entries
        if len(entries) > self.max_entries:
            entries = entries[-self.max_entries :]

        # Ensure parent directory exists and write to file
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        except OSError:
            pass
