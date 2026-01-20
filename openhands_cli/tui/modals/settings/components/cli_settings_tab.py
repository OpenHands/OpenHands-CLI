"""CLI Settings tab component for the settings modal."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Label, Static, Switch

from openhands_cli.stores import CliSettings


class SettingsSwitch(Container):
    """Reusable switch component for settings forms."""

    def __init__(
        self,
        label: str,
        description: str,
        switch_id: str,
        value: bool = False,
        **kwargs,
    ):
        """Initialize the settings switch.

        Args:
            label: The label text for the switch
            description: Help text describing the setting
            switch_id: Unique ID for the switch widget
            value: Initial value of the switch
        """
        super().__init__(classes="form_group", **kwargs)
        self._label = label
        self._description = description
        self._switch_id = switch_id
        self._value = value

    def compose(self) -> ComposeResult:
        """Compose the switch with label and description."""
        with Horizontal(classes="switch_container"):
            yield Label(f"{self._label}:", classes="form_label switch_label")
            yield Switch(value=self._value, id=self._switch_id, classes="form_switch")
        yield Static(self._description, classes="form_help switch_help")


class CliSettingsTab(Container):
    """CLI Settings tab component containing CLI-specific settings."""

    def __init__(self, **kwargs):
        """Initialize the CLI settings tab."""
        super().__init__(**kwargs)
        self.cli_settings = CliSettings.load()

    def compose(self) -> ComposeResult:
        """Compose the CLI settings tab content."""
        with VerticalScroll(id="cli_settings_content"):
            yield Static("CLI Settings", classes="form_section_title")

            yield SettingsSwitch(
                label="Default Cells Expanded",
                description=(
                    "When enabled, new action/observation cells will be expanded "
                    "by default. When disabled, cells will be collapsed showing "
                    "only the title. Use Ctrl+O to toggle all cells at any time."
                ),
                switch_id="default_cells_expanded_switch",
                value=self.cli_settings.default_cells_expanded,
            )

            yield SettingsSwitch(
                label="Auto-open Plan Panel",
                description=(
                    "When enabled, the plan panel will automatically open on the "
                    "right side when the agent first uses the task tracker. "
                    "You can toggle it anytime via the command palette."
                ),
                switch_id="auto_open_plan_panel_switch",
                value=self.cli_settings.auto_open_plan_panel,
            )

    def get_cli_settings(self) -> CliSettings:
        """Get the current CLI settings from the form."""
        default_cells_expanded_switch = self.query_one(
            "#default_cells_expanded_switch", Switch
        )
        auto_open_plan_panel_switch = self.query_one(
            "#auto_open_plan_panel_switch", Switch
        )

        return CliSettings(
            default_cells_expanded=default_cells_expanded_switch.value,
            auto_open_plan_panel=auto_open_plan_panel_switch.value,
        )
