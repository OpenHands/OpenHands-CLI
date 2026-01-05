"""CLI Settings tab component for the settings modal."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Label, Static, Switch

from openhands_cli.stores import CliSettings


class CliSettingsTab(Container):
    """CLI Settings tab component containing CLI-specific settings."""

    def __init__(self, **kwargs):
        """Initialize the CLI settings tab."""
        super().__init__(**kwargs)
        self.cli_settings = CliSettings.load()

    def compose(self) -> ComposeResult:
        """Compose the CLI settings tab content."""
        with Container(id="cli_settings_content"):
            yield Static(
                "CLI Settings",
                classes="form_section_title",
            )

            # Display Cost Per Action Setting
            with Container(classes="form_group"):
                with Horizontal(classes="switch_container"):
                    yield Label(
                        "Display Cost Per Action:",
                        classes="form_label switch_label",
                    )
                    yield Switch(
                        value=self.cli_settings.display_cost_per_action,
                        id="display_cost_switch",
                        classes="form_switch",
                    )
                yield Static(
                    "Show the estimated cost for each action performed "
                    "by the agent in the interface.",
                    classes="form_help switch_help",
                )

            # Default Cells Expanded Setting
            with Container(classes="form_group"):
                with Horizontal(classes="switch_container"):
                    yield Label(
                        "Default Cells Expanded:",
                        classes="form_label switch_label",
                    )
                    yield Switch(
                        value=self.cli_settings.default_cells_expanded,
                        id="default_cells_expanded_switch",
                        classes="form_switch",
                    )
                yield Static(
                    "When enabled, new action/observation cells will be expanded "
                    "by default. When disabled, cells will be collapsed showing "
                    "only the title. Use Ctrl+O to toggle all cells at any time.",
                    classes="form_help switch_help",
                )

    def get_cli_settings(self) -> CliSettings:
        """Get the current CLI settings from the form."""
        display_cost_switch = self.query_one("#display_cost_switch", Switch)
        default_cells_expanded_switch = self.query_one(
            "#default_cells_expanded_switch", Switch
        )

        return CliSettings(
            display_cost_per_action=display_cost_switch.value,
            default_cells_expanded=default_cells_expanded_switch.value,
        )
