"""Search screen for prompt history."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from openhands_cli.stores.prompt_history import PromptHistoryEntry, PromptHistoryStore


# Maximum number of search results to display in the history search modal
MAX_SEARCH_RESULTS = 100


class HistorySearchScreen(ModalScreen[str | None]):
    """A modal screen for searching through prompt history.

    Returns the selected prompt text, or None if cancelled.
    """

    BINDINGS: ClassVar = [
        Binding("escape", "dismiss(None)", "Cancel"),
        Binding("ctrl+q", "request_quit", "Quit", priority=True),
        Binding("ctrl+c", "request_quit", "Quit", priority=True, show=False),
    ]

    DEFAULT_CSS = """
    HistorySearchScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.8);
    }

    #search_container {
        width: 80;
        height: 80%;
        background: $surface;
        border: round $primary;
        padding: 1;
    }

    #search_input {
        margin-bottom: 0;
        border: round $primary 50%;
    }

    #results_info {
        height: 1;
        margin-bottom: 1;
        content-align: right middle;
        color: $text-muted;
    }

    #results_list {
        height: 1fr;
        border: round $primary 30%;
        background: $surface;
    }

    /* Ensure highlight is visible even when not focused */
    #results_list .option-list--option-highlighted {
        background: $primary 30%;
    }

    #results_list:focus .option-list--option-highlighted {
        background: $primary;
        color: $background;
    }

    .help_text {
        color: $text-muted;
        margin-top: 1;
        text-align: center;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.history_store = PromptHistoryStore()
        self._all_entries: list[PromptHistoryEntry] = []
        self._option_full_texts: dict[int, str] = {}  # option index -> full text

    def compose(self) -> ComposeResult:
        with Vertical(id="search_container"):
            yield Static("Search History (Fuzzy Matching)", classes="form_label")
            yield Input(placeholder="Type to search...", id="search_input")
            yield Static("", id="results_info")

            yield OptionList(id="results_list")

            yield Static(
                "↑/↓ to navigate • Enter to select • Esc to cancel", classes="help_text"
            )

    def on_mount(self) -> None:
        """Load history when mounted."""
        self._all_entries = self.history_store.load_entries()

        self._update_results("")
        self.query_one("#search_input").focus()

    @on(Input.Changed, "#search_input")
    def _on_input_changed(self, event: Input.Changed) -> None:
        """Update results as the user types."""
        self._update_results(event.value)

    def _update_results(self, search_text: str) -> None:
        """Filter and display results based on search text."""
        option_list = self.query_one("#results_list", OptionList)
        info_label = self.query_one("#results_info", Static)

        option_list.clear_options()
        self._option_full_texts.clear()  # Clear stale texts from previous search

        search_terms = search_text.lower().split()

        match_count = 0
        for entry in self._all_entries:
            text = entry["text"]
            text_lower = text.lower()

            if all(term in text_lower for term in search_terms):
                # Create the highlighted rich text for the option
                rich_text = self._format_history_item(
                    text, entry["timestamp"], search_terms
                )
                option_list.add_option(Option(rich_text, id=f"opt_{match_count}"))
                # Store the full text in our dictionary for retrieval
                self._option_full_texts[match_count] = text

                match_count += 1
                if match_count >= MAX_SEARCH_RESULTS:
                    break

        if match_count > 0:
            option_list.highlighted = 0
        else:
            option_list.add_option(Option("No matches found", disabled=True))

        # Update info label
        total = len(self._all_entries)
        info_label.update(f"Showing {match_count} of {total} prompts")

    def _format_history_item(
        self, full_text: str, timestamp: str, search_terms: list[str]
    ) -> Text:
        """Create formatted rich text for a history item."""
        raw_text = full_text.replace("\n", " ").strip()

        try:
            dt = datetime.fromisoformat(timestamp)
            date_str = dt.strftime("%y-%m-%d %H:%M")
        except (ValueError, TypeError):
            date_str = "Unknown"

        # Find best window to show matches
        if search_terms:
            first_match_idx = -1
            lower_text = raw_text.lower()
            for term in search_terms:
                idx = lower_text.find(term)
                if idx != -1:
                    if first_match_idx == -1 or idx < first_match_idx:
                        first_match_idx = idx

            if first_match_idx > 30:
                start = first_match_idx - 30
                end = start + 100
                display_plain = "..." + raw_text[start:end]
            else:
                display_plain = raw_text[:100]

            display_text = Text(display_plain)
            for term in search_terms:
                display_text.highlight_words(
                    [term], style="bold reverse italic", case_sensitive=False
                )
        else:
            display_text = Text(raw_text[:100])

        result = Text()
        result.append(display_text)
        result.append(f"  ({date_str})", style="dim")
        return result

    def _dismiss_option(self, option_id: str | None) -> bool:
        """Dismiss with the full text for the given option ID.

        Returns True if dismissed.
        """
        if option_id is not None and option_id.startswith("opt_"):
            opt_idx = int(option_id[4:])
            if opt_idx in self._option_full_texts:
                self.dismiss(self._option_full_texts[opt_idx])
                return True
        return False

    @on(OptionList.OptionSelected)
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle selection of a history item."""
        self._dismiss_option(event.option.id)

    def on_key(self, event: events.Key) -> None:
        """Handle global keys for the modal."""
        if event.key == "enter" and self.query_one("#search_input").has_focus:
            # If Enter is pressed while in the search box, select the highlighted item
            option_list = self.query_one("#results_list", OptionList)
            if option_list.highlighted is not None:
                selected_option = option_list.get_option_at_index(
                    option_list.highlighted
                )
                if self._dismiss_option(selected_option.id):
                    event.prevent_default()
                    event.stop()
        elif event.key in ("up", "down") and self.query_one("#search_input").has_focus:
            self.query_one("#results_list").focus()
            event.prevent_default()
            event.stop()

    def action_request_quit(self) -> None:
        """Delegate quit request to the main app."""
        app = self.app
        if app is not None:
            # Type-safe way to call action_request_quit if it exists
            quit_action = getattr(app, "action_request_quit", None)
            if quit_action is not None:
                quit_action()
