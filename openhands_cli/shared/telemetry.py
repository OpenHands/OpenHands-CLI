"""Shared telemetry module for PostHog analytics.

This module provides a centralized telemetry client for sending analytics events
to PostHog. It respects user preferences for telemetry collection and handles
all PostHog interactions in a consistent manner.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from posthog import Posthog


if TYPE_CHECKING:
    from openhands.sdk.conversation.stats import (  # pyright: ignore[reportMissingImports]
        CombinedMetrics,
    )


# PostHog configuration
POSTHOG_API_KEY = "phc_QkAtbXVsh3Ja0Pw4IK696cxYEmr20Bx1kbnI7QtOCqg"
POSTHOG_HOST = "https://us.i.posthog.com"


class TelemetryClient:
    """Centralized telemetry client for PostHog analytics.

    This client handles all telemetry events and respects user preferences
    for data collection. It provides methods for tracking various events
    like conversations, agent messages, user messages, and LLM metrics.
    """

    _instance: TelemetryClient | None = None
    _posthog: Posthog | None = None

    def __new__(cls) -> TelemetryClient:
        """Singleton pattern to ensure only one telemetry client exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the telemetry client."""
        if self._posthog is None:
            self._posthog = Posthog(
                project_api_key=POSTHOG_API_KEY,
                host=POSTHOG_HOST,
            )

    @staticmethod
    def is_telemetry_enabled() -> bool:
        """Check if telemetry is enabled based on user settings.

        Telemetry is enabled if:
        1. The user has explicitly enabled it in settings, OR
        2. The user has critic enabled (telemetry is required for critic)

        Returns:
            True if telemetry should be collected, False otherwise.
        """
        from openhands_cli.stores import CliSettings

        settings = CliSettings.load()
        # Telemetry is required if critic is enabled
        if settings.enable_critic:
            return True
        return settings.enable_telemetry

    def capture(
        self,
        distinct_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Capture a telemetry event if telemetry is enabled.

        Args:
            distinct_id: Unique identifier for the user/session
            event: Name of the event to capture
            properties: Optional dictionary of event properties
        """
        if not self.is_telemetry_enabled():
            return

        if self._posthog is None:
            return

        try:
            self._posthog.capture(
                distinct_id=distinct_id,
                event=event,
                properties=properties or {},
            )
            self._posthog.flush()
        except Exception:
            # Silently fail if PostHog submission fails
            pass

    def track_conversation_start(
        self,
        conversation_id: str,
        agent_model: str | None = None,
    ) -> None:
        """Track the start of a new conversation.

        Args:
            conversation_id: Unique identifier for the conversation
            agent_model: The agent's model name (e.g., "claude-sonnet-4-5-20250929")
        """
        properties: dict[str, Any] = {
            "timestamp": time.time(),
        }
        if agent_model:
            properties["agent_model"] = agent_model

        self.capture(
            distinct_id=conversation_id,
            event="conversation_start",
            properties=properties,
        )

    def track_user_message(
        self,
        conversation_id: str,
        message_index: int,
        agent_model: str | None = None,
    ) -> None:
        """Track a user message event.

        Args:
            conversation_id: Unique identifier for the conversation
            message_index: Index of the message in the conversation
            agent_model: The agent's model name
        """
        properties: dict[str, Any] = {
            "timestamp": time.time(),
            "message_index": message_index,
        }
        if agent_model:
            properties["agent_model"] = agent_model

        self.capture(
            distinct_id=conversation_id,
            event="user_message",
            properties=properties,
        )

    def track_agent_message(
        self,
        conversation_id: str,
        message_index: int,
        agent_model: str | None = None,
        is_finish: bool = False,
    ) -> None:
        """Track an agent message or finish event.

        Args:
            conversation_id: Unique identifier for the conversation
            message_index: Index of the message in the conversation
            agent_model: The agent's model name
            is_finish: Whether this is a finish event
        """
        properties: dict[str, Any] = {
            "timestamp": time.time(),
            "message_index": message_index,
            "is_finish": is_finish,
        }
        if agent_model:
            properties["agent_model"] = agent_model

        event_name = "agent_finish" if is_finish else "agent_message"
        self.capture(
            distinct_id=conversation_id,
            event=event_name,
            properties=properties,
        )

    def track_llm_metrics(
        self,
        conversation_id: str,
        combined_metrics: CombinedMetrics | None,
        agent_model: str | None = None,
    ) -> None:
        """Track LLM metrics including token usage and cache hit rate.

        Args:
            conversation_id: Unique identifier for the conversation
            combined_metrics: Combined metrics from the conversation
            agent_model: The agent's model name
        """
        if combined_metrics is None:
            return

        properties: dict[str, Any] = {
            "timestamp": time.time(),
        }

        if agent_model:
            properties["agent_model"] = agent_model

        # Add accumulated cost
        if combined_metrics.accumulated_cost is not None:
            properties["accumulated_cost"] = combined_metrics.accumulated_cost

        # Add token usage metrics
        usage = combined_metrics.accumulated_token_usage
        if usage:
            properties["prompt_tokens"] = usage.prompt_tokens or 0
            properties["completion_tokens"] = usage.completion_tokens or 0
            properties["cache_read_tokens"] = usage.cache_read_tokens or 0
            properties["cache_creation_tokens"] = usage.cache_creation_tokens or 0
            properties["context_window"] = usage.context_window or 0

            # Calculate cache hit rate
            prompt = usage.prompt_tokens or 0
            cache_read = usage.cache_read_tokens or 0
            if prompt > 0:
                properties["cache_hit_rate"] = cache_read / prompt
            else:
                properties["cache_hit_rate"] = 0.0

        # Add per-request metrics from the last request
        token_usages = combined_metrics.token_usages
        if token_usages:
            last_usage = token_usages[-1]
            properties["last_request_prompt_tokens"] = last_usage.prompt_tokens or 0
            properties["last_request_completion_tokens"] = (
                last_usage.completion_tokens or 0
            )
            properties["last_request_cache_read_tokens"] = (
                last_usage.cache_read_tokens or 0
            )
            properties["last_request_cache_creation_tokens"] = (
                last_usage.cache_creation_tokens or 0
            )

        self.capture(
            distinct_id=conversation_id,
            event="llm_metrics",
            properties=properties,
        )

    def track_critic_inference(
        self,
        conversation_id: str,
        critic_score: float,
        critic_success: bool,
        agent_model: str | None = None,
        event_ids: list[str] | None = None,
    ) -> None:
        """Track a critic inference event.

        Args:
            conversation_id: Unique identifier for the conversation
            critic_score: The critic's score prediction
            critic_success: Whether the critic predicts success
            agent_model: The agent's model name
            event_ids: List of event IDs for reproducibility
        """
        properties: dict[str, Any] = {
            "critic_score": critic_score,
            "critic_success": critic_success,
            "conversation_id": conversation_id,
        }

        if agent_model:
            properties["agent_model"] = agent_model

        if event_ids:
            properties["event_ids"] = event_ids

        self.capture(
            distinct_id=conversation_id,
            event="critic_inference",
            properties=properties,
        )

    def track_critic_feedback(
        self,
        conversation_id: str,
        feedback_type: str,
        critic_score: float,
        critic_success: bool,
        agent_model: str | None = None,
        event_ids: list[str] | None = None,
    ) -> None:
        """Track user feedback on critic predictions.

        Args:
            conversation_id: Unique identifier for the conversation
            feedback_type: Type of feedback (accurate, too_high, too_low,
                not_applicable)
            critic_score: The critic's score prediction
            critic_success: Whether the critic predicts success
            agent_model: The agent's model name
            event_ids: List of event IDs for reproducibility
        """
        properties: dict[str, Any] = {
            "feedback_type": feedback_type,
            "critic_score": critic_score,
            "critic_success": critic_success,
            "conversation_id": conversation_id,
        }

        if agent_model:
            properties["agent_model"] = agent_model

        if event_ids:
            properties["event_ids"] = event_ids

        self.capture(
            distinct_id=conversation_id,
            event="critic_feedback",
            properties=properties,
        )


# Global telemetry client instance
_telemetry_client: TelemetryClient | None = None


def get_telemetry_client() -> TelemetryClient:
    """Get the global telemetry client instance.

    Returns:
        The singleton TelemetryClient instance.
    """
    global _telemetry_client
    if _telemetry_client is None:
        _telemetry_client = TelemetryClient()
    return _telemetry_client
