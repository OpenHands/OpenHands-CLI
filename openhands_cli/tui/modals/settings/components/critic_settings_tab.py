"""Critic Settings tab component for the settings modal."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Checkbox, Input, Label, Static

from openhands_cli.stores.cli_settings import (
    DEFAULT_CRITIC_THRESHOLD,
    DEFAULT_ISSUE_THRESHOLD,
    CriticSettings,
)

from .cli_settings_tab import SettingsSwitch


class ThresholdInput(Container):
    """Input component for critic threshold with label and description."""

    DEFAULT_CSS = """
    ThresholdInput .validation_error {
        color: $error;
        display: none;
        margin-top: 0;
        height: auto;
    }

    ThresholdInput.invalid .validation_error {
        display: block;
    }

    ThresholdInput.invalid .threshold_input {
        border: tall $error;
    }
    """

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
        yield Static("Value must be between 1 and 100", classes="validation_error")

    def validate_input(self, value: str) -> bool:
        """Validate the input value and update visual state.

        Args:
            value: The input value to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            int_value = int(value)
            is_valid = 1 <= int_value <= 100
        except (ValueError, TypeError):
            is_valid = False

        if is_valid:
            self.remove_class("invalid")
        else:
            self.add_class("invalid")

        return is_valid


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

    def __init__(self, initial_settings: CriticSettings | None = None, **kwargs):
        """Initialize the Critic settings tab.

        Args:
            initial_settings: Optional CriticSettings object with initial values.
                If not provided, uses defaults.
        """
        super().__init__(**kwargs)
        self._initial_settings = initial_settings or CriticSettings()

    def compose(self) -> ComposeResult:
        """Compose the Critic settings tab content."""
        enable_critic = self._initial_settings.enable_critic
        enable_refinement = self._initial_settings.enable_iterative_refinement
        threshold = self._initial_settings.critic_threshold
        issue_threshold = self._initial_settings.issue_threshold

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
                value=enable_critic,
            )

            yield SettingsSwitch(
                label="Enable Iterative Refinement",
                description=(
                    "When enabled, if the critic predicts a low success probability "
                    "OR detects a specific issue (e.g., insufficient testing) above "
                    "the issue threshold, a follow-up message is automatically sent "
                    "to the agent asking it to review and improve its work."
                ),
                switch_id="enable_iterative_refinement_switch",
                value=enable_refinement,
            )

            default_pct = int(DEFAULT_CRITIC_THRESHOLD * 100)
            yield ThresholdInput(
                label="Refinement Threshold",
                description=(
                    f"The overall critic score threshold (1-100%) below which "
                    f"iterative refinement is triggered. Default: {default_pct}%. "
                    "Lower values mean refinement only triggers for very low scores."
                ),
                input_id="critic_threshold_input",
                value=threshold,
                disabled=not enable_refinement,
            )

            issue_default_pct = int(DEFAULT_ISSUE_THRESHOLD * 100)
            yield ThresholdInput(
                label="Issue Detection Threshold",
                description=(
                    f"The threshold (1-100%) for individual issue detection. "
                    f"Default: {issue_default_pct}%. When any specific issue "
                    "(e.g., Insufficient Testing, Loop Behavior) has probability "
                    "above this threshold, refinement is triggered even if the "
                    "overall score is acceptable."
                ),
                input_id="issue_threshold_input",
                value=issue_threshold,
                disabled=not enable_refinement,
            )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes to enable/disable threshold inputs."""
        if event.checkbox.id == "enable_iterative_refinement_switch":
            try:
                threshold_input = self.query_one("#critic_threshold_input", Input)
                threshold_input.disabled = not event.value
                issue_threshold_input = self.query_one("#issue_threshold_input", Input)
                issue_threshold_input.disabled = not event.value
            except NoMatches:
                # Widget not yet mounted or was removed; safe to ignore during
                # composition lifecycle
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes to validate threshold values."""
        if event.input.id in ("critic_threshold_input", "issue_threshold_input"):
            try:
                # Find the parent ThresholdInput container and validate
                threshold_container = event.input.ancestors_with_self
                for ancestor in threshold_container:
                    if isinstance(ancestor, ThresholdInput):
                        ancestor.validate_input(event.value)
                        break
            except NoMatches:
                pass

    def get_updated_fields(self) -> dict[str, Any]:
        """Return only the fields this tab manages.

        Returns:
            Dict with 'enable_critic', 'enable_iterative_refinement',
            'critic_threshold', and 'issue_threshold' values.
        """
        enable_critic_switch = self.query_one("#enable_critic_switch", Checkbox)
        enable_refinement_switch = self.query_one(
            "#enable_iterative_refinement_switch", Checkbox
        )
        threshold_input = self.query_one("#critic_threshold_input", Input)
        issue_threshold_input = self.query_one("#issue_threshold_input", Input)

        # Parse and validate threshold values (convert from percentage to 0-1 range)
        threshold = self._parse_threshold(
            threshold_input.value, DEFAULT_CRITIC_THRESHOLD
        )
        issue_threshold = self._parse_threshold(
            issue_threshold_input.value, DEFAULT_ISSUE_THRESHOLD
        )

        return {
            "enable_critic": enable_critic_switch.value,
            "enable_iterative_refinement": enable_refinement_switch.value,
            "critic_threshold": threshold,
            "issue_threshold": issue_threshold,
        }

    def _parse_threshold(self, value: str, default: float) -> float:
        """Parse a threshold value from percentage string to float.

        Args:
            value: The input value as percentage string (e.g., "60")
            default: Default value to use if parsing fails

        Returns:
            Float between 0.0 and 1.0
        """
        try:
            threshold_percent = int(value)
            if not 1 <= threshold_percent <= 100:
                return default
            return threshold_percent / 100.0
        except (ValueError, TypeError):
            return default
