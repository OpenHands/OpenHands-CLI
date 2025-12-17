"""App Configurations tab component for the settings modal."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Label, Static, Switch

from openhands_cli.refactor.modals.settings.app_config import AppConfiguration


class AppConfigurationsTab(Container):
    """App Configurations tab component containing application-specific settings."""

    def __init__(self, **kwargs):
        """Initialize the app configurations tab."""
        super().__init__(**kwargs)
        self.app_config = AppConfiguration.load()

    def compose(self) -> ComposeResult:
        """Compose the app configurations tab content."""
        with Container(id="app_config_content"):
            yield Static(
                "App Configurations",
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
                        value=self.app_config.display_cost_per_action,
                        id="display_cost_switch",
                        classes="form_switch",
                    )
                yield Static(
                    "Show the estimated cost for each action performed "
                    "by the agent in the interface.",
                    classes="form_help switch_help",
                )

    def get_app_config(self) -> AppConfiguration:
        """Get the current app configuration from the form."""
        display_cost_switch = self.query_one("#display_cost_switch", Switch)

        return AppConfiguration(display_cost_per_action=display_cost_switch.value)
