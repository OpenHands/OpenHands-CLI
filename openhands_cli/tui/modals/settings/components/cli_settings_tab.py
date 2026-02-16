"""CLI Settings tab component for the settings modal."""

from textual import on
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
        disabled: bool = False,
        **kwargs,
    ):
        """Initialize the settings switch.

        Args:
            label: The label text for the switch
            description: Help text describing the setting
            switch_id: Unique ID for the switch widget
            value: Initial value of the switch
            disabled: Whether the switch is disabled
        """
        super().__init__(classes="form_group", **kwargs)
        self._label = label
        self._description = description
        self._switch_id = switch_id
        self._value = value
        self._disabled = disabled

    def compose(self) -> ComposeResult:
        """Compose the switch with label and description."""
        with Horizontal(classes="switch_container"):
            yield Label(f"{self._label}:", classes="form_label switch_label")
            yield Switch(
                value=self._value,
                id=self._switch_id,
                classes="form_switch",
                disabled=self._disabled,
            )
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

            yield SettingsSwitch(
                label="Enable Critic (Experimental)",
                description=(
                    "When enabled and using OpenHands LLM provider, an experimental "
                    "critic model predicts task success likelihood in real-time. "
                    "We collect anonymized data (IDs, critic response, feedback) to "
                    "evaluate accuracy. See: https://openhands.dev/privacy"
                ),
                switch_id="enable_critic_switch",
                value=self.cli_settings.enable_critic,
            )

            # Telemetry is forced on when critic is enabled
            telemetry_forced = self.cli_settings.enable_critic
            telemetry_description = (
                "When enabled, anonymous usage metrics are collected to help "
                "improve OpenHands CLI. This includes conversation counts, "
                "message timing, and LLM cache hit rates."
            )
            if telemetry_forced:
                telemetry_description += (
                    " [bold]Note:[/bold] Telemetry cannot be disabled while "
                    "Critic is enabled."
                )

            yield SettingsSwitch(
                label="Enable Telemetry",
                description=telemetry_description,
                switch_id="enable_telemetry_switch",
                value=self.cli_settings.enable_telemetry or telemetry_forced,
                disabled=telemetry_forced,
            )

    def on_mount(self) -> None:
        """Update telemetry switch state based on critic setting."""
        self._update_telemetry_switch_state()

    @on(Switch.Changed, "#enable_critic_switch")
    def _on_critic_changed(self, _event: Switch.Changed) -> None:
        """Handle critic switch changes to update telemetry switch state."""
        self._update_telemetry_switch_state()

    def _update_telemetry_switch_state(self) -> None:
        """Update telemetry switch based on critic setting.

        When critic is enabled, telemetry must be enabled and cannot be disabled.
        """
        try:
            critic_switch = self.query_one("#enable_critic_switch", Switch)
            telemetry_switch = self.query_one("#enable_telemetry_switch", Switch)

            if critic_switch.value:
                # Force telemetry on when critic is enabled
                telemetry_switch.value = True
                telemetry_switch.disabled = True
            else:
                # Allow user to toggle telemetry when critic is disabled
                telemetry_switch.disabled = False
        except Exception:
            # Widget may not be mounted yet
            pass

    def get_cli_settings(self) -> CliSettings:
        """Get the current CLI settings from the form."""
        default_cells_expanded_switch = self.query_one(
            "#default_cells_expanded_switch", Switch
        )
        auto_open_plan_panel_switch = self.query_one(
            "#auto_open_plan_panel_switch", Switch
        )
        enable_critic_switch = self.query_one("#enable_critic_switch", Switch)
        enable_telemetry_switch = self.query_one("#enable_telemetry_switch", Switch)

        return CliSettings(
            default_cells_expanded=default_cells_expanded_switch.value,
            auto_open_plan_panel=auto_open_plan_panel_switch.value,
            enable_critic=enable_critic_switch.value,
            enable_telemetry=enable_telemetry_switch.value,
        )
