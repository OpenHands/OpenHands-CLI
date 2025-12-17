"""App Configurations tab component for the settings modal."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Label, Static, Switch


class AppConfigurationsTab(Container):
    """App Configurations tab component containing application-specific settings."""

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
                        value=False,
                        id="display_cost_switch",
                        classes="form_switch",
                    )
                yield Static(
                    "Show the estimated cost for each action performed "
                    "by the agent in the interface.",
                    classes="form_help switch_help",
                )