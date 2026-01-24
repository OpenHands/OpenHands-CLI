"""Tests for the critic feedback widget."""

from unittest.mock import MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button

from openhands.sdk.critic.result import CriticResult
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.utils.critic.feedback import (
    CriticFeedbackWidget,
    send_critic_inference_event,
)


class CriticFeedbackTestApp(App):
    """Minimal Textual App that mounts a CriticFeedbackWidget."""

    def __init__(self, widget: CriticFeedbackWidget) -> None:
        super().__init__()
        self.widget = widget
        self.register_theme(OPENHANDS_THEME)
        self.theme = "openhands"

    def compose(self) -> ComposeResult:
        yield self.widget


@pytest.mark.asyncio
async def test_critic_feedback_initial_render() -> None:
    """Test that the feedback widget renders with buttons."""
    critic_result = CriticResult(score=0.85, message="Test message")

    widget = CriticFeedbackWidget(
        critic_result=critic_result, conversation_id="test-conv-id"
    )

    app = CriticFeedbackTestApp(widget)

    async with app.run_test() as _pilot:
        # Check that all buttons are present
        buttons = widget.query(Button)
        button_ids = [btn.id for btn in buttons]
        assert "btn-accurate" in button_ids
        assert "btn-too_high" in button_ids
        assert "btn-too_low" in button_ids
        assert "btn-not_applicable" in button_ids
        assert "btn-dismiss" in button_ids


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.get_telemetry_client")
async def test_critic_feedback_submit_feedback(mock_get_client: MagicMock) -> None:
    """Test that feedback is sent to PostHog when user presses a key."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    critic_result = CriticResult(score=0.85, message="Test message")

    widget = CriticFeedbackWidget(
        critic_result=critic_result, conversation_id="test-conv-id"
    )

    app = CriticFeedbackTestApp(widget)

    async with app.run_test() as pilot:
        # Focus the widget
        widget.focus()
        await pilot.pause()

        # Press key "1" for "accurate"
        await pilot.press("1")
        await pilot.pause(0.1)

        # Verify telemetry client was called
        mock_client.track_critic_feedback.assert_called_once()
        call_args = mock_client.track_critic_feedback.call_args
        assert call_args.kwargs["conversation_id"] == "test-conv-id"
        assert call_args.kwargs["feedback_type"] == "accurate"
        assert call_args.kwargs["critic_score"] == 0.85
        assert call_args.kwargs["critic_success"] is True


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.get_telemetry_client")
async def test_critic_feedback_dismiss_no_analytics(
    mock_get_client: MagicMock,
) -> None:
    """Test that dismissing (key 0) doesn't send analytics."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    critic_result = CriticResult(score=0.85, message="Test message")

    widget = CriticFeedbackWidget(
        critic_result=critic_result, conversation_id="test-conv-id"
    )

    app = CriticFeedbackTestApp(widget)

    async with app.run_test() as pilot:
        # Focus the widget
        widget.focus()
        await pilot.pause()

        # Press key "0" for dismiss
        await pilot.press("0")
        await pilot.pause(0.1)

        # Verify telemetry client was NOT called
        mock_client.track_critic_feedback.assert_not_called()


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.get_telemetry_client")
async def test_critic_feedback_different_options(
    mock_get_client: MagicMock,
) -> None:
    """Test that different feedback options are correctly recorded."""
    feedback_options = [
        ("1", "accurate"),
        ("2", "too_high"),
        ("3", "too_low"),
        ("4", "not_applicable"),
    ]

    for key, expected_feedback in feedback_options:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        critic_result = CriticResult(score=0.75, message="Test")

        widget = CriticFeedbackWidget(
            critic_result=critic_result, conversation_id="test-conv"
        )

        app = CriticFeedbackTestApp(widget)

        async with app.run_test() as pilot:
            widget.focus()
            await pilot.pause()

            await pilot.press(key)
            await pilot.pause(0.1)

            # Verify the correct feedback type was sent
            call_args = mock_client.track_critic_feedback.call_args
            assert call_args.kwargs["feedback_type"] == expected_feedback, (
                f"Failed for key {key}"
            )


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.get_telemetry_client")
async def test_critic_feedback_includes_event_ids(
    mock_get_client: MagicMock,
) -> None:
    """Test that event_ids from metadata are included in PostHog request."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Create critic result with event_ids in metadata
    critic_result = CriticResult(
        score=0.85,
        message="Test message",
        metadata={"event_ids": ["event1", "event2", "event3"]},
    )

    widget = CriticFeedbackWidget(
        critic_result=critic_result, conversation_id="test-conv-id"
    )

    app = CriticFeedbackTestApp(widget)

    async with app.run_test() as pilot:
        widget.focus()
        await pilot.pause()

        # Submit feedback (key "1" for "just about right")
        await pilot.press("1")
        await pilot.pause(0.1)

        # Verify event_ids are included in properties
        call_args = mock_client.track_critic_feedback.call_args
        assert call_args.kwargs["event_ids"] == [
            "event1",
            "event2",
            "event3",
        ]
        assert call_args.kwargs["conversation_id"] == "test-conv-id"


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.get_telemetry_client")
async def test_critic_feedback_without_event_ids(
    mock_get_client: MagicMock,
) -> None:
    """Test that feedback works correctly when event_ids are not present."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Create critic result without metadata
    critic_result = CriticResult(score=0.85, message="Test message")

    widget = CriticFeedbackWidget(
        critic_result=critic_result, conversation_id="test-conv-id"
    )

    app = CriticFeedbackTestApp(widget)

    async with app.run_test() as pilot:
        widget.focus()
        await pilot.pause()

        # Submit feedback (key "1" for "just about right")
        await pilot.press("1")
        await pilot.pause(0.1)

        # Verify event_ids are None when not provided
        call_args = mock_client.track_critic_feedback.call_args
        assert call_args.kwargs["event_ids"] is None
        assert call_args.kwargs["conversation_id"] == "test-conv-id"


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.get_telemetry_client")
async def test_critic_feedback_includes_agent_model(
    mock_get_client: MagicMock,
) -> None:
    """Test that agent_model is included in PostHog request when provided."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    critic_result = CriticResult(score=0.85, message="Test message")

    widget = CriticFeedbackWidget(
        critic_result=critic_result,
        conversation_id="test-conv-id",
        agent_model="claude-sonnet-4-5-20250929",
    )

    app = CriticFeedbackTestApp(widget)

    async with app.run_test() as pilot:
        widget.focus()
        await pilot.pause()

        await pilot.press("1")
        await pilot.pause(0.1)

        # Verify agent_model is included in properties
        call_args = mock_client.track_critic_feedback.call_args
        assert call_args.kwargs["agent_model"] == "claude-sonnet-4-5-20250929"


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.get_telemetry_client")
async def test_critic_feedback_button_click(mock_get_client: MagicMock) -> None:
    """Test that clicking a button submits feedback."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    critic_result = CriticResult(score=0.85, message="Test message")

    widget = CriticFeedbackWidget(
        critic_result=critic_result, conversation_id="test-conv-id"
    )

    app = CriticFeedbackTestApp(widget)

    async with app.run_test() as pilot:
        # Click the "accurate" button
        await pilot.click("#btn-accurate")
        await pilot.pause(0.1)

        # Verify telemetry client was called
        mock_client.track_critic_feedback.assert_called_once()
        call_args = mock_client.track_critic_feedback.call_args
        assert call_args.kwargs["feedback_type"] == "accurate"


@patch("openhands_cli.tui.utils.critic.feedback.get_telemetry_client")
def test_send_critic_inference_event(mock_get_client: MagicMock) -> None:
    """Test that send_critic_inference_event sends the correct event."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    critic_result = CriticResult(
        score=0.85,
        message="Test message",
        metadata={"event_ids": ["event1", "event2"]},
    )

    send_critic_inference_event(
        critic_result=critic_result,
        conversation_id="test-conv-id",
        agent_model="claude-sonnet-4-5-20250929",
    )

    # Verify telemetry client was called with correct event
    mock_client.track_critic_inference.assert_called_once()
    call_args = mock_client.track_critic_inference.call_args
    assert call_args.kwargs["conversation_id"] == "test-conv-id"
    assert call_args.kwargs["critic_score"] == 0.85
    assert call_args.kwargs["critic_success"] is True
    assert call_args.kwargs["agent_model"] == "claude-sonnet-4-5-20250929"
    assert call_args.kwargs["event_ids"] == ["event1", "event2"]


@patch("openhands_cli.tui.utils.critic.feedback.get_telemetry_client")
def test_send_critic_inference_event_without_agent_model(
    mock_get_client: MagicMock,
) -> None:
    """Test that send_critic_inference_event works without agent_model."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    critic_result = CriticResult(score=0.75, message="Test")

    send_critic_inference_event(
        critic_result=critic_result,
        conversation_id="test-conv-id",
    )

    # Verify agent_model is None when not provided
    call_args = mock_client.track_critic_inference.call_args
    assert call_args.kwargs["agent_model"] is None
