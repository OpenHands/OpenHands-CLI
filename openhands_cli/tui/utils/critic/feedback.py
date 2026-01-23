"""Critic feedback widget for collecting user feedback on critic predictions."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, ClassVar

from posthog import Posthog
from textual import events, on
from textual.containers import Horizontal
from textual.widgets import Button, Static


if TYPE_CHECKING:
    from openhands.sdk.critic.result import CriticResult


# PostHog configuration
POSTHOG_API_KEY = "phc_QkAtbXVsh3Ja0Pw4IK696cxYEmr20Bx1kbnI7QtOCqg"
POSTHOG_HOST = "https://us.i.posthog.com"


def send_critic_inference_event(
    critic_result: CriticResult,
    conversation_id: str,
    agent_model: str | None = None,
) -> None:
    """Send a PostHog event when critic inference produces output.

    This is called when the critic result is displayed to the user,
    before they provide any feedback.

    Args:
        critic_result: The critic result from inference
        conversation_id: The conversation ID for tracking
        agent_model: The agent's model name (e.g., "claude-sonnet-4-5-20250929")
    """
    try:
        posthog = Posthog(
            project_api_key=POSTHOG_API_KEY,
            host=POSTHOG_HOST,
        )

        properties = {
            "critic_score": critic_result.score,
            "critic_success": critic_result.success,
            "conversation_id": conversation_id,
        }

        # Add agent model if available
        if agent_model:
            properties["agent_model"] = agent_model

        # Add event_ids from metadata if available for reproducibility
        if critic_result.metadata and "event_ids" in critic_result.metadata:
            properties["event_ids"] = critic_result.metadata["event_ids"]

        posthog.capture(
            distinct_id=conversation_id,
            event="critic_inference",
            properties=properties,
        )
        posthog.flush()
    except Exception:
        # Silently fail if PostHog submission fails
        pass


class CriticFeedbackWidget(Static, can_focus=True):
    """Widget for collecting user feedback on critic predictions.

    Displays options for user to rate the critic's prediction accuracy.
    Sends feedback to PostHog when user makes a selection.
    """

    DEFAULT_CSS = """
    CriticFeedbackWidget {
        height: auto;
        background: transparent;
        color: $foreground;
        padding: 0 1;
        margin: 1 0;
    }

    CriticFeedbackWidget Horizontal {
        height: auto;
        width: 100%;
        margin-top: 1;
    }

    CriticFeedbackWidget Button {
        width: 12;
        margin-right: 1;
        border: none;
        background: $surface-darken-1;
        color: $foreground;
    }

    CriticFeedbackWidget Button:hover {
        background: $surface-lighten-1;
    }
    """

    FEEDBACK_OPTIONS: ClassVar[dict[str, str]] = {
        "0": "dismiss",
        "1": "accurate",
        "2": "too_high",
        "3": "too_low",
        "4": "not_applicable",
    }

    BUTTON_LABELS: ClassVar[dict[str, str]] = {
        "accurate": "[1] Accurate",
        "too_high": "[2] Too high",
        "too_low": "[3] Too low",
        "not_applicable": "[4] N/A",
        "dismiss": "[0] Dismiss",
    }

    def __init__(
        self,
        critic_result: CriticResult,
        conversation_id: str | None = None,
        agent_model: str | None = None,
        **kwargs,
    ) -> None:
        """Initialize the critic feedback widget.

        Args:
            critic_result: The critic result this feedback is for
            conversation_id: Optional conversation ID for tracking
            agent_model: Optional agent model name for tracking
            **kwargs: Additional arguments for Static widget
        """
        super().__init__(**kwargs)
        self.critic_result = critic_result
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.agent_model = agent_model
        self._feedback_submitted = False

        # Initialize PostHog client
        self._posthog = Posthog(
            project_api_key=POSTHOG_API_KEY,
            host=POSTHOG_HOST,
        )

    def compose(self):
        """Compose the widget with prompt and buttons."""
        yield Static(
            "[bold]Does the critic's success prediction align with your "
            "perception?[/bold]",
            id="feedback-prompt",
        )
        with Horizontal():
            yield Button(
                self.BUTTON_LABELS["accurate"], id="btn-accurate", compact=True
            )
            yield Button(
                self.BUTTON_LABELS["too_high"], id="btn-too_high", compact=True
            )
            yield Button(self.BUTTON_LABELS["too_low"], id="btn-too_low", compact=True)
            yield Button(
                self.BUTTON_LABELS["not_applicable"],
                id="btn-not_applicable",
                compact=True,
            )
            yield Button(self.BUTTON_LABELS["dismiss"], id="btn-dismiss", compact=True)

    def on_mount(self) -> None:
        """Auto-focus the widget when mounted so users can immediately press keys."""
        self.focus()

    @on(Button.Pressed, "#btn-accurate")
    async def handle_accurate(self) -> None:
        """Handle accurate button press."""
        await self._submit_feedback("accurate")

    @on(Button.Pressed, "#btn-too_high")
    async def handle_too_high(self) -> None:
        """Handle too high button press."""
        await self._submit_feedback("too_high")

    @on(Button.Pressed, "#btn-too_low")
    async def handle_too_low(self) -> None:
        """Handle too low button press."""
        await self._submit_feedback("too_low")

    @on(Button.Pressed, "#btn-not_applicable")
    async def handle_not_applicable(self) -> None:
        """Handle N/A button press."""
        await self._submit_feedback("not_applicable")

    @on(Button.Pressed, "#btn-dismiss")
    async def handle_dismiss(self) -> None:
        """Handle dismiss button press."""
        await self._submit_feedback("dismiss")

    async def on_key(self, event: events.Key) -> None:
        """Handle key press events.

        Args:
            event: The key event
        """
        if self._feedback_submitted:
            return

        if event.character in self.FEEDBACK_OPTIONS:
            feedback_type = self.FEEDBACK_OPTIONS[event.character]
            await self._submit_feedback(feedback_type)
            event.stop()
            event.prevent_default()

    async def _submit_feedback(self, feedback_type: str) -> None:
        """Submit feedback to PostHog and remove the widget.

        Args:
            feedback_type: The type of feedback (dismiss, overestimation, etc.)
        """
        if self._feedback_submitted:
            return

        self._feedback_submitted = True

        # Don't send analytics for dismiss
        if feedback_type != "dismiss":
            try:
                # Build properties dict with base fields
                properties = {
                    "feedback_type": feedback_type,
                    "critic_score": self.critic_result.score,
                    "critic_success": self.critic_result.success,
                    "conversation_id": self.conversation_id,
                }

                # Add agent model if available
                if self.agent_model:
                    properties["agent_model"] = self.agent_model

                # Add event_ids from metadata if available for reproducibility
                if (
                    self.critic_result.metadata
                    and "event_ids" in self.critic_result.metadata
                ):
                    properties["event_ids"] = self.critic_result.metadata["event_ids"]

                self._posthog.capture(
                    distinct_id=self.conversation_id,
                    event="critic_feedback",
                    properties=properties,
                )
                # Flush to ensure the event is sent
                self._posthog.flush()
            except Exception:
                # Silently fail if PostHog submission fails
                pass

        # Update to show feedback was recorded or clear for dismiss
        prompt = self.query_one("#feedback-prompt", Static)
        buttons = self.query(Button)

        if feedback_type != "dismiss":
            prompt.update("✓ Thank you for your feedback!")
            for btn in buttons:
                btn.display = False
        else:
            prompt.update("")
            for btn in buttons:
                btn.display = False

        # Remove the widget after a brief delay (or immediately for dismiss)
        if feedback_type == "dismiss":
            self.remove()
        else:
            # Wait 2 seconds before removing
            self.set_timer(2.0, self.remove)
