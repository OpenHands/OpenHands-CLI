"""Tests for the critic feedback widget."""

from unittest.mock import MagicMock, patch

import pytest
from textual.app import App, ComposeResult

from openhands.sdk.critic.result import CriticResult
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.utils.critic.feedback import CriticFeedbackWidget


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
    """Test that the feedback widget renders with the correct message."""
    critic_result = CriticResult(score=0.85, message="Test message")

    widget = CriticFeedbackWidget(
        critic_result=critic_result, conversation_id="test-conv-id"
    )

    app = CriticFeedbackTestApp(widget)

    async with app.run_test() as _pilot:
        rendered_text = str(widget.content)
        assert "Does the critic's prediction align" in rendered_text
        # Check for bold-formatted option numbers
        assert "[bold][0][/bold] Dismiss" in rendered_text
        assert "[bold][1][/bold] Accurate" in rendered_text
        assert "[bold][2][/bold] Too high" in rendered_text
        assert "[bold][3][/bold] Too low" in rendered_text
        assert "[bold][4][/bold] N/A" in rendered_text


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.Posthog")
async def test_critic_feedback_submit_feedback(mock_posthog_class: MagicMock) -> None:
    """Test that feedback is sent to PostHog when user presses a key."""
    mock_posthog = MagicMock()
    mock_posthog_class.return_value = mock_posthog

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

        # Verify PostHog capture was called
        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args
        assert call_args.kwargs["distinct_id"] == "test-conv-id"
        assert call_args.kwargs["event"] == "critic_feedback"
        assert call_args.kwargs["properties"]["feedback_type"] == "accurate"
        assert call_args.kwargs["properties"]["critic_score"] == 0.85
        assert call_args.kwargs["properties"]["critic_success"] is True

        # Verify flush was called
        mock_posthog.flush.assert_called_once()


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.Posthog")
async def test_critic_feedback_dismiss_no_analytics(
    mock_posthog_class: MagicMock,
) -> None:
    """Test that dismissing (key 0) doesn't send analytics."""
    mock_posthog = MagicMock()
    mock_posthog_class.return_value = mock_posthog

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

        # Verify PostHog capture was NOT called
        mock_posthog.capture.assert_not_called()
        mock_posthog.flush.assert_not_called()


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.Posthog")
async def test_critic_feedback_different_options(
    mock_posthog_class: MagicMock,
) -> None:
    """Test that different feedback options are correctly recorded."""
    feedback_options = [
        ("1", "accurate"),
        ("2", "too_high"),
        ("3", "too_low"),
        ("4", "not_applicable"),
    ]

    for key, expected_feedback in feedback_options:
        mock_posthog = MagicMock()
        mock_posthog_class.return_value = mock_posthog

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
            call_args = mock_posthog.capture.call_args
            assert (
                call_args.kwargs["properties"]["feedback_type"] == expected_feedback
            ), f"Failed for key {key}"


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.Posthog")
async def test_critic_feedback_includes_event_ids(
    mock_posthog_class: MagicMock,
) -> None:
    """Test that event_ids from metadata are included in PostHog request."""
    mock_posthog = MagicMock()
    mock_posthog_class.return_value = mock_posthog

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
        call_args = mock_posthog.capture.call_args
        assert call_args.kwargs["properties"]["event_ids"] == [
            "event1",
            "event2",
            "event3",
        ]
        assert call_args.kwargs["properties"]["conversation_id"] == "test-conv-id"


@pytest.mark.asyncio
@patch("openhands_cli.tui.utils.critic.feedback.Posthog")
async def test_critic_feedback_without_event_ids(
    mock_posthog_class: MagicMock,
) -> None:
    """Test that feedback works correctly when event_ids are not present."""
    mock_posthog = MagicMock()
    mock_posthog_class.return_value = mock_posthog

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

        # Verify event_ids are NOT in properties when not provided
        call_args = mock_posthog.capture.call_args
        assert "event_ids" not in call_args.kwargs["properties"]
        assert call_args.kwargs["properties"]["conversation_id"] == "test-conv-id"
