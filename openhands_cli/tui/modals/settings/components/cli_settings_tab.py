"""CLI Settings tab component for the settings modal."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Label, Static, Switch

from openhands_cli.stores.cli_settings import CliSettings
from openhands_cli.stores.programmatic_settings import CliProgrammaticSettings


class CliSettingsScroll(VerticalScroll, can_focus=False):
    pass


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

    def __init__(self, initial_settings: CliSettings | None = None, **kwargs):
        """Initialize the CLI settings tab.

        Args:
            initial_settings: Optional CliSettings object with initial values.
                If not provided, uses defaults.
        """
        super().__init__(**kwargs)
        self._initial_settings = initial_settings or CliSettings()

    def compose(self) -> ComposeResult:
        """Compose the CLI settings tab content."""
        cli_fields = [
            field
            for section in CliProgrammaticSettings.export_schema().sections
            if section.key == "cli"
            for field in section.fields
        ]

        with CliSettingsScroll(id="cli_settings_content"):
            yield Static("CLI Settings", classes="form_section_title")
            for field in cli_fields:
                leaf_key = field.key.split(".")[-1]
                yield SettingsSwitch(
                    label=field.label,
                    description=field.description or "",
                    switch_id=f"{leaf_key}_switch",
                    value=bool(getattr(self._initial_settings, leaf_key)),
                )

    def get_updated_fields(self) -> dict[str, Any]:
        """Return only the fields this tab manages."""
        cli_fields = [
            field
            for section in CliProgrammaticSettings.export_schema().sections
            if section.key == "cli"
            for field in section.fields
        ]
        return {
            field.key.split(".")[-1]: self.query_one(
                f"#{field.key.split('.')[-1]}_switch", Switch
            ).value
            for field in cli_fields
        }
