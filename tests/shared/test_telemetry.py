"""Tests for the shared telemetry module."""

from unittest.mock import MagicMock, patch

from openhands_cli.shared.telemetry import TelemetryClient, get_telemetry_client


class TestTelemetryClient:
    """Tests for the TelemetryClient class."""

    def setup_method(self):
        """Reset the singleton instance before each test."""
        TelemetryClient._instance = None
        TelemetryClient._posthog = None

    @patch("openhands_cli.shared.telemetry.Posthog")
    def test_singleton_pattern(self, mock_posthog_class: MagicMock) -> None:
        """Test that TelemetryClient follows singleton pattern."""
        client1 = TelemetryClient()
        client2 = TelemetryClient()
        assert client1 is client2

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_is_telemetry_enabled_when_enabled(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test that telemetry is enabled when setting is True."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = True
        mock_settings.enable_critic = False
        mock_load.return_value = mock_settings

        assert TelemetryClient.is_telemetry_enabled() is True

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_is_telemetry_enabled_when_disabled(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test that telemetry is disabled when setting is False."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = False
        mock_settings.enable_critic = False
        mock_load.return_value = mock_settings

        assert TelemetryClient.is_telemetry_enabled() is False

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_is_telemetry_enabled_when_critic_enabled(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test that telemetry is forced on when critic is enabled."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = False  # Even if telemetry is disabled
        mock_settings.enable_critic = True  # Critic forces telemetry on
        mock_load.return_value = mock_settings

        assert TelemetryClient.is_telemetry_enabled() is True

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_capture_when_telemetry_disabled(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test that capture does nothing when telemetry is disabled."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = False
        mock_settings.enable_critic = False
        mock_load.return_value = mock_settings

        mock_posthog = MagicMock()
        mock_posthog_class.return_value = mock_posthog

        client = TelemetryClient()
        client.capture("test-id", "test_event", {"key": "value"})

        # PostHog capture should not be called
        mock_posthog.capture.assert_not_called()

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_capture_when_telemetry_enabled(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test that capture sends event when telemetry is enabled."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = True
        mock_settings.enable_critic = False
        mock_load.return_value = mock_settings

        mock_posthog = MagicMock()
        mock_posthog_class.return_value = mock_posthog

        client = TelemetryClient()
        client.capture("test-id", "test_event", {"key": "value"})

        # PostHog capture should be called
        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args
        assert call_args.kwargs["distinct_id"] == "test-id"
        assert call_args.kwargs["event"] == "test_event"
        assert call_args.kwargs["properties"] == {"key": "value"}
        mock_posthog.flush.assert_called_once()

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_track_conversation_start(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test tracking conversation start event."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = True
        mock_settings.enable_critic = False
        mock_load.return_value = mock_settings

        mock_posthog = MagicMock()
        mock_posthog_class.return_value = mock_posthog

        client = TelemetryClient()
        client.track_conversation_start(
            conversation_id="conv-123",
            agent_model="claude-sonnet-4-5-20250929",
        )

        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args
        assert call_args.kwargs["distinct_id"] == "conv-123"
        assert call_args.kwargs["event"] == "conversation_start"
        assert "timestamp" in call_args.kwargs["properties"]
        assert (
            call_args.kwargs["properties"]["agent_model"]
            == "claude-sonnet-4-5-20250929"
        )

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_track_user_message(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test tracking user message event."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = True
        mock_settings.enable_critic = False
        mock_load.return_value = mock_settings

        mock_posthog = MagicMock()
        mock_posthog_class.return_value = mock_posthog

        client = TelemetryClient()
        client.track_user_message(
            conversation_id="conv-123",
            message_index=1,
            agent_model="claude-sonnet-4-5-20250929",
        )

        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args
        assert call_args.kwargs["distinct_id"] == "conv-123"
        assert call_args.kwargs["event"] == "user_message"
        assert call_args.kwargs["properties"]["message_index"] == 1
        assert "timestamp" in call_args.kwargs["properties"]

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_track_critic_inference(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test tracking critic inference event."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = True
        mock_settings.enable_critic = True
        mock_load.return_value = mock_settings

        mock_posthog = MagicMock()
        mock_posthog_class.return_value = mock_posthog

        client = TelemetryClient()
        client.track_critic_inference(
            conversation_id="conv-123",
            critic_score=0.85,
            critic_success=True,
            agent_model="claude-sonnet-4-5-20250929",
            event_ids=["event1", "event2"],
        )

        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args
        assert call_args.kwargs["distinct_id"] == "conv-123"
        assert call_args.kwargs["event"] == "critic_inference"
        assert call_args.kwargs["properties"]["critic_score"] == 0.85
        assert call_args.kwargs["properties"]["critic_success"] is True
        assert call_args.kwargs["properties"]["event_ids"] == ["event1", "event2"]

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_track_critic_feedback(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test tracking critic feedback event."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = True
        mock_settings.enable_critic = True
        mock_load.return_value = mock_settings

        mock_posthog = MagicMock()
        mock_posthog_class.return_value = mock_posthog

        client = TelemetryClient()
        client.track_critic_feedback(
            conversation_id="conv-123",
            feedback_type="accurate",
            critic_score=0.85,
            critic_success=True,
            agent_model="claude-sonnet-4-5-20250929",
        )

        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args
        assert call_args.kwargs["distinct_id"] == "conv-123"
        assert call_args.kwargs["event"] == "critic_feedback"
        assert call_args.kwargs["properties"]["feedback_type"] == "accurate"
        assert call_args.kwargs["properties"]["critic_score"] == 0.85

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_track_llm_metrics(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test tracking LLM metrics event."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = True
        mock_settings.enable_critic = False
        mock_load.return_value = mock_settings

        mock_posthog = MagicMock()
        mock_posthog_class.return_value = mock_posthog

        # Create mock combined metrics
        mock_token_usage = MagicMock()
        mock_token_usage.prompt_tokens = 1000
        mock_token_usage.completion_tokens = 500
        mock_token_usage.cache_read_tokens = 800
        mock_token_usage.cache_creation_tokens = 200
        mock_token_usage.context_window = 128000

        mock_combined_metrics = MagicMock()
        mock_combined_metrics.accumulated_cost = 0.05
        mock_combined_metrics.accumulated_token_usage = mock_token_usage
        mock_combined_metrics.token_usages = [mock_token_usage]

        client = TelemetryClient()
        client.track_llm_metrics(
            conversation_id="conv-123",
            combined_metrics=mock_combined_metrics,
            agent_model="claude-sonnet-4-5-20250929",
        )

        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args
        assert call_args.kwargs["distinct_id"] == "conv-123"
        assert call_args.kwargs["event"] == "llm_metrics"
        props = call_args.kwargs["properties"]
        assert props["accumulated_cost"] == 0.05
        assert props["prompt_tokens"] == 1000
        assert props["completion_tokens"] == 500
        assert props["cache_read_tokens"] == 800
        assert props["cache_hit_rate"] == 0.8  # 800/1000

    @patch("openhands_cli.shared.telemetry.Posthog")
    @patch("openhands_cli.stores.cli_settings.CliSettings.load")
    def test_track_llm_metrics_with_none(
        self, mock_load: MagicMock, mock_posthog_class: MagicMock
    ) -> None:
        """Test that track_llm_metrics handles None metrics gracefully."""
        mock_settings = MagicMock()
        mock_settings.enable_telemetry = True
        mock_settings.enable_critic = False
        mock_load.return_value = mock_settings

        mock_posthog = MagicMock()
        mock_posthog_class.return_value = mock_posthog

        client = TelemetryClient()
        client.track_llm_metrics(
            conversation_id="conv-123",
            combined_metrics=None,
            agent_model="claude-sonnet-4-5-20250929",
        )

        # Should not capture anything when metrics are None
        mock_posthog.capture.assert_not_called()


class TestGetTelemetryClient:
    """Tests for the get_telemetry_client function."""

    def setup_method(self):
        """Reset the singleton instance before each test."""
        TelemetryClient._instance = None
        TelemetryClient._posthog = None
        # Also reset the global client
        import openhands_cli.shared.telemetry as telemetry_module

        telemetry_module._telemetry_client = None

    @patch("openhands_cli.shared.telemetry.Posthog")
    def test_get_telemetry_client_returns_singleton(
        self, mock_posthog_class: MagicMock
    ) -> None:
        """Test that get_telemetry_client returns the same instance."""
        client1 = get_telemetry_client()
        client2 = get_telemetry_client()
        assert client1 is client2
