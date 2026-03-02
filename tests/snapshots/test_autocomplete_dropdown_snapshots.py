"""Snapshot tests for the AutoCompleteDropdown widget.

These tests verify that the autocomplete dropdown renders correctly
above the input field, at full width, with aligned command descriptions,
and that it does not get occluded by the input widgets.

To update snapshots when intentional changes are made:
    pytest tests/snapshots/ --snapshot-update

To run these tests:
    pytest tests/snapshots/test_autocomplete_dropdown_snapshots.py
"""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Static
from textual_autocomplete import DropdownItem

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.widgets.user_input.input_field import InputField


# Subset of real commands for deterministic snapshots
TEST_COMMANDS = [
    DropdownItem(main="/help - Display available commands"),
    DropdownItem(main="/new - Start a new conversation"),
    DropdownItem(main="/history - Toggle conversation history"),
    DropdownItem(main="/settings - Open settings"),
    DropdownItem(main="/confirm - Configure confirmation settings"),
    DropdownItem(main="/condense - Condense conversation history"),
    DropdownItem(main="/skills - View loaded skills, hooks, and MCPs"),
    DropdownItem(main="/feedback - Send anonymous feedback about CLI"),
    DropdownItem(main="/exit - Exit the application"),
]


class AutocompleteTestApp(App):
    """Test app that renders InputField with autocomplete dropdown."""

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
    }
    #chat_area {
        height: 1fr;
        background: $background;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.register_theme(OPENHANDS_THEME)
        self.theme = "openhands"

    def compose(self) -> ComposeResult:
        yield Static("Chat messages would appear here...", id="chat_area")
        yield InputField(placeholder="Type a message...")
        yield Footer()


class TestAutocompleteDropdownSnapshots:
    """Snapshot tests for the autocomplete dropdown positioning and rendering."""

    def test_dropdown_hidden_by_default(self, snap_compare):
        """Dropdown should not be visible when no trigger character is typed."""
        assert snap_compare(AutocompleteTestApp(), terminal_size=(100, 30))

    def test_dropdown_visible_with_slash(self, snap_compare):
        """
        Dropdown should appear above the input when / is typed,
        showing all commands.
        """

        async def type_slash(pilot):
            input_field = pilot.app.query_one(InputField)
            # Override commands for deterministic output
            input_field.autocomplete.command_candidates = TEST_COMMANDS
            input_field.single_line_widget.text = "/"
            input_field.single_line_widget.move_cursor(
                input_field.single_line_widget.document.end
            )
            input_field.autocomplete.update_candidates()
            await pilot.pause()

        assert snap_compare(
            AutocompleteTestApp(),
            terminal_size=(100, 30),
            run_before=type_slash,
        )

    def test_dropdown_filtered_commands(self, snap_compare):
        """Dropdown should filter commands as the user types more characters."""

        async def type_partial_command(pilot):
            input_field = pilot.app.query_one(InputField)
            input_field.autocomplete.command_candidates = TEST_COMMANDS
            input_field.single_line_widget.text = "/co"
            input_field.single_line_widget.move_cursor(
                input_field.single_line_widget.document.end
            )
            input_field.autocomplete.update_candidates()
            await pilot.pause()

        assert snap_compare(
            AutocompleteTestApp(),
            terminal_size=(100, 30),
            run_before=type_partial_command,
        )

    def test_dropdown_not_occluded_by_input(self, snap_compare):
        """Dropdown should render above (not behind) the input widget.

        This tests the compose order: autocomplete is yielded before
        the input widgets so it appears above them in the vertical layout.
        """

        async def show_dropdown(pilot):
            input_field = pilot.app.query_one(InputField)
            input_field.autocomplete.command_candidates = TEST_COMMANDS
            input_field.single_line_widget.text = "/h"
            input_field.single_line_widget.move_cursor(
                input_field.single_line_widget.document.end
            )
            input_field.autocomplete.update_candidates()
            await pilot.pause()

        assert snap_compare(
            AutocompleteTestApp(),
            terminal_size=(100, 30),
            run_before=show_dropdown,
        )
