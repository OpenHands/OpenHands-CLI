"""CLI Settings tab component for the settings modal."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Input, Label, Static, Switch

from openhands_cli.stores.cli_settings import CliSettings, DEFAULT_MARKETPLACE_PATH


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


class SettingsInput(Container):
    """Reusable text input component for settings forms."""

    def __init__(
        self,
        label: str,
        description: str,
        input_id: str,
        value: str = "",
        placeholder: str = "",
        **kwargs,
    ):
        """Initialize the settings input.

        Args:
            label: The label text for the input
            description: Help text describing the setting
            input_id: Unique ID for the input widget
            value: Initial value of the input
            placeholder: Placeholder text for the input
        """
        super().__init__(classes="form_group", **kwargs)
        self._label = label
        self._description = description
        self._input_id = input_id
        self._value = value
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        """Compose the input with label and description."""
        yield Label(f"{self._label}:", classes="form_label")
        yield Input(
            value=self._value,
            id=self._input_id,
            classes="form_input",
            placeholder=self._placeholder,
        )
        yield Static(self._description, classes="form_help")


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
                value=self._initial_settings.default_cells_expanded,
            )

            yield SettingsSwitch(
                label="Auto-open Plan Panel",
                description=(
                    "When enabled, the plan panel will automatically open on the "
                    "right side when the agent first uses the task tracker. "
                    "You can toggle it anytime via the command palette."
                ),
                switch_id="auto_open_plan_panel_switch",
                value=self._initial_settings.auto_open_plan_panel,
            )

            yield Static("Skills Settings", classes="form_section_title")

            yield SettingsInput(
                label="Marketplace Path",
                description=(
                    "Path to the marketplace JSON file that defines which skills are loaded. "
                    "Supports formats: 'marketplaces/default.json' (default repo), "
                    "'owner/repo:path/to/marketplace.json' (custom repo), or leave empty "
                    "to load all skills without filtering."
                ),
                input_id="marketplace_path_input",
                value=self._initial_settings.marketplace_path or "",
                placeholder=DEFAULT_MARKETPLACE_PATH,
            )

    def get_updated_fields(self) -> dict[str, Any]:
        """Return only the fields this tab manages.

        Returns:
            Dict with CLI settings values.
        """
        marketplace_value = self.query_one("#marketplace_path_input", Input).value
        return {
            "default_cells_expanded": self.query_one(
                "#default_cells_expanded_switch", Switch
            ).value,
            "auto_open_plan_panel": self.query_one(
                "#auto_open_plan_panel_switch", Switch
            ).value,
            "marketplace_path": marketplace_value if marketplace_value else None,
        }
