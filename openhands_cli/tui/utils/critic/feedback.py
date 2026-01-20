"""Critic feedback widget for collecting user feedback on critic predictions."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, ClassVar

from posthog import Posthog
from textual import events
from textual.widgets import Static


if TYPE_CHECKING:
    from openhands.sdk.critic.result import CriticResult


class CriticFeedbackWidget(Static, can_focus=True):
    """Widget for collecting user feedback on critic predictions.

    Displays options for user to rate the critic's prediction accuracy.
    Sends feedback to PostHog when user makes a selection.
    """

    DEFAULT_CSS = """
    CriticFeedbackWidget {
        height: auto;
        background: $surface;
        color: $text;
        border: solid $primary;
        padding: 1 2;
        margin: 0 0 1 0;
    }

    CriticFeedbackWidget:focus {
        border: solid $accent;
    }
    """

    FEEDBACK_OPTIONS: ClassVar[dict[str, str]] = {
        "0": "dismiss",
        "1": "overestimation",
        "2": "underestimation",
        "3": "just about right",
        "4": "doesn't make sense",
    }

    def __init__(
        self,
        critic_result: CriticResult,
        conversation_id: str | None = None,
        **kwargs,
    ) -> None:
        """Initialize the critic feedback widget.

        Args:
            critic_result: The critic result this feedback is for
            conversation_id: Optional conversation ID for tracking
            **kwargs: Additional arguments for Static widget
        """
        super().__init__(**kwargs)
        self.critic_result = critic_result
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self._feedback_submitted = False

        # Initialize PostHog client
        self._posthog = Posthog(
            project_api_key="phc_QkAtbXVsh3Ja0Pw4IK696cxYEmr20Bx1kbnI7QtOCqg",
            host="https://us.i.posthog.com",
        )

        # Set initial message
        self.update(self._build_message())

    def on_mount(self) -> None:
        """Auto-focus the widget when mounted so users can immediately press keys."""
        self.focus()

    def _build_message(self) -> str:
        """Build the feedback prompt message."""
        return (
            "Does the critic's prediction align with your perception?\n"
            "[0] Dismiss  [1] Overestimation  [2] Underestimation  "
            "[3] Just about right  [4] Doesn't make sense"
        )

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

        # Update message to show feedback was recorded
        if feedback_type != "dismiss":
            self.update("✓ Thank you for your feedback!")
        else:
            self.update("")

        # Remove the widget after a brief delay (or immediately for dismiss)
        if feedback_type == "dismiss":
            self.remove()
        else:
            # Wait 2 seconds before removing
            self.set_timer(2.0, self.remove)
