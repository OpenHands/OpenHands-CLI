"""CLI Settings tab component for the settings modal."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Label, Select, Static, Switch

from openhands_cli.stores.cli_settings import CliSettings


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


def _get_theme_options(current_theme: str) -> list[tuple[str, str]]:
    """Build (label, value) pairs for the theme selector.

    Includes every built-in Textual theme plus the custom ``openhands`` theme.
    The list is sorted alphabetically with *openhands* always first.
    """
    from textual.app import App

    names = set(App().available_themes) | {"openhands"}
    if current_theme:
        names.add(current_theme)
    ordered = sorted(names - {"openhands"})
    ordered.insert(0, "openhands")
    return [(name, name) for name in ordered]


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
        with CliSettingsScroll(id="cli_settings_content"):
            yield Static("CLI Settings", classes="form_section_title")

            with Container(classes="form_group"):
                yield Label("Theme:", classes="form_label")
                yield Select(
                    _get_theme_options(self._initial_settings.theme),
                    value=self._initial_settings.theme,
                    id="theme_select",
                    allow_blank=False,
                )
                yield Static(
                    "Color theme for the terminal UI. "
                    "Changes take effect on next launch.",
                    classes="form_help",
                )

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

    def get_updated_fields(self) -> dict[str, Any]:
        """Return only the fields this tab manages.

        Returns:
            Dict with 'theme', 'default_cells_expanded', and
            'auto_open_plan_panel' values.
        """
        return {
            "theme": str(self.query_one("#theme_select", Select).value),
            "default_cells_expanded": self.query_one(
                "#default_cells_expanded_switch", Switch
            ).value,
            "auto_open_plan_panel": self.query_one(
                "#auto_open_plan_panel_switch", Switch
            ).value,
        }
