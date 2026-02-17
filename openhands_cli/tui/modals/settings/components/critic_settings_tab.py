"""Critic Settings tab component for the settings modal."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Input, Label, Static, Switch

from openhands_cli.stores import CliSettings
from openhands_cli.stores.cli_settings import DEFAULT_CRITIC_THRESHOLD

from .cli_settings_tab import SettingsSwitch


class ThresholdInput(Container):
    """Input component for critic threshold with label and description."""

    def __init__(
        self,
        label: str,
        description: str,
        input_id: str,
        value: float,
        disabled: bool = False,
        **kwargs,
    ):
        """Initialize the threshold input.

        Args:
            label: The label text for the input
            description: Help text describing the setting
            input_id: Unique ID for the input widget
            value: Initial value (0.0-1.0)
            disabled: Whether the input is initially disabled
        """
        super().__init__(classes="form_group", **kwargs)
        self._label = label
        self._description = description
        self._input_id = input_id
        self._value = value
        self._disabled = disabled

    def compose(self) -> ComposeResult:
        """Compose the input with label and description."""
        with Horizontal(classes="threshold_container"):
            yield Label(f"{self._label}:", classes="form_label threshold_label")
            yield Input(
                value=f"{int(self._value * 100)}",
                id=self._input_id,
                classes="form_input threshold_input",
                type="integer",
                max_length=3,
                disabled=self._disabled,
            )
            yield Label("%", classes="threshold_suffix")
        yield Static(self._description, classes="form_help threshold_help")


class CriticSettingsTab(Container):
    """Critic Settings tab component containing critic-related settings."""

    DEFAULT_CSS = """
    .threshold_container {
        height: auto;
        align: left middle;
    }

    .threshold_input {
        width: 8;
    }

    .threshold_label {
        width: auto;
        margin-right: 1;
    }

    .threshold_suffix {
        width: 2;
        margin-left: 1;
    }

    .threshold_help {
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs):
        """Initialize the Critic settings tab."""
        super().__init__(**kwargs)
        self.cli_settings = CliSettings.load()

    def compose(self) -> ComposeResult:
        """Compose the Critic settings tab content."""
        with VerticalScroll(id="critic_settings_content"):
            yield Static("Critic Settings (Experimental)", classes="form_section_title")

            yield SettingsSwitch(
                label="Enable Critic Score Display",
                description=(
                    "When enabled and using OpenHands LLM provider, an experimental "
                    "critic model predicts task success likelihood in real-time. "
                    "The score is displayed after each agent action. "
                    "We collect anonymized data (IDs, critic response, feedback) to "
                    "evaluate accuracy. See: https://openhands.dev/privacy"
                ),
                switch_id="enable_critic_switch",
                value=self.cli_settings.enable_critic,
            )

            yield SettingsSwitch(
                label="Enable Iterative Refinement",
                description=(
                    "When enabled, if the critic predicts a low success probability, "
                    "a follow-up message is automatically sent to the agent asking it "
                    "to review and improve its work. This helps the agent self-correct "
                    "when initial attempts may be incomplete."
                ),
                switch_id="enable_iterative_refinement_switch",
                value=self.cli_settings.enable_iterative_refinement,
            )

            yield ThresholdInput(
                label="Refinement Threshold",
                description=(
                    f"The critic score threshold (1-100%) below which iterative "
                    f"refinement is triggered. Default: {int(DEFAULT_CRITIC_THRESHOLD * 100)}%. "
                    "Lower values mean refinement only triggers for very low scores."
                ),
                input_id="critic_threshold_input",
                value=self.cli_settings.critic_threshold,
                disabled=not self.cli_settings.enable_iterative_refinement,
            )

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch changes to enable/disable threshold input."""
        if event.switch.id == "enable_iterative_refinement_switch":
            try:
                threshold_input = self.query_one("#critic_threshold_input", Input)
                threshold_input.disabled = not event.value
            except Exception:
                pass

    def get_critic_settings(self) -> dict:
        """Get the current critic settings from the form.

        Returns:
            Dictionary with critic-related settings
        """
        enable_critic_switch = self.query_one("#enable_critic_switch", Switch)
        enable_refinement_switch = self.query_one(
            "#enable_iterative_refinement_switch", Switch
        )
        threshold_input = self.query_one("#critic_threshold_input", Input)

        # Parse threshold value (convert from percentage to 0-1 range)
        try:
            threshold_percent = int(threshold_input.value)
            threshold = max(0.0, min(1.0, threshold_percent / 100.0))
        except (ValueError, TypeError):
            threshold = DEFAULT_CRITIC_THRESHOLD

        return {
            "enable_critic": enable_critic_switch.value,
            "enable_iterative_refinement": enable_refinement_switch.value,
            "critic_threshold": threshold,
        }
