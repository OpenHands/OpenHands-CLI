"""Tests for the iterative refinement utilities."""

from unittest.mock import MagicMock

import pytest
from textual.app import App
from textual.containers import VerticalScroll

from openhands.sdk import Message, TextContent
from openhands.sdk.critic.result import CriticResult
from openhands.sdk.event import MessageEvent
from openhands_cli.stores import CliSettings, CriticSettings
from openhands_cli.tui.utils.critic.refinement import (
    build_refinement_message,
    should_trigger_refinement,
)
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


class TestShouldTriggerRefinement:
    """Tests for should_trigger_refinement function."""

    def test_disabled_returns_false(self):
        """When disabled, should always return False regardless of score."""
        result = CriticResult(score=0.1, message="Low score")
        assert not should_trigger_refinement(result, threshold=0.5, enabled=False)

    def test_none_result_returns_false(self):
        """When critic result is None, should return False."""
        assert not should_trigger_refinement(None, threshold=0.5, enabled=True)

    def test_score_below_threshold_returns_true(self):
        """When score is below threshold and enabled, should return True."""
        result = CriticResult(score=0.3, message="Low score")
        assert should_trigger_refinement(result, threshold=0.5, enabled=True)

    def test_score_at_threshold_returns_false(self):
        """When score equals threshold, should return False (not below)."""
        result = CriticResult(score=0.5, message="At threshold")
        assert not should_trigger_refinement(result, threshold=0.5, enabled=True)

    def test_score_above_threshold_returns_false(self):
        """When score is above threshold, should return False."""
        result = CriticResult(score=0.8, message="Good score")
        assert not should_trigger_refinement(result, threshold=0.5, enabled=True)

    def test_custom_threshold(self):
        """Custom threshold should be respected."""
        result = CriticResult(score=0.6, message="Medium score")
        # Should NOT trigger with default threshold of 0.5
        assert not should_trigger_refinement(result, threshold=0.5, enabled=True)
        # Should trigger with higher threshold of 0.7
        assert should_trigger_refinement(result, threshold=0.7, enabled=True)


class TestBuildRefinementMessage:
    """Tests for build_refinement_message function."""

    def test_basic_message_structure(self):
        """Test that message has expected structure and content."""
        result = CriticResult(score=0.3, message="Low score")
        message = build_refinement_message(result, threshold=0.5)

        # Check score mentioned
        assert "30.0%" in message

        # Check threshold mentioned
        assert "50%" in message

        # Check instruction to review
        assert "Please review your work carefully" in message

    def test_includes_review_instructions(self):
        """Test that message includes review instructions."""
        result = CriticResult(score=0.4, message="Issues detected")
        message = build_refinement_message(result, threshold=0.5)

        # Check for review steps
        assert "requirements" in message.lower()
        assert "complete and correct" in message.lower()

    def test_handles_missing_metadata(self):
        """Test that message works without metadata."""
        result = CriticResult(score=0.3, message="Simple message")
        message = build_refinement_message(result, threshold=0.5)

        # Should still have basic structure
        assert "30.0%" in message
        assert "Please review" in message

    def test_threshold_formatting(self):
        """Test various threshold values are formatted correctly."""
        result = CriticResult(score=0.2, message="Test")

        # Test decimal threshold
        message = build_refinement_message(result, threshold=0.75)
        assert "75%" in message

        # Test integer-like threshold
        message = build_refinement_message(result, threshold=1.0)
        assert "100%" in message

    def test_message_is_concise(self):
        """Test that the message follows SDK pattern of being concise."""
        result = CriticResult(score=0.4, message="Test")
        message = build_refinement_message(result, threshold=0.6)

        # Message should be relatively short (SDK style is concise)
        lines = message.strip().split("\n")
        # Should have score line, iteration line, empty line, instruction, and steps
        assert len(lines) <= 10

    def test_iteration_info_included(self):
        """Test that iteration info is included in the message."""
        result = CriticResult(score=0.3, message="Low score")
        message = build_refinement_message(
            result, threshold=0.5, iteration=2, max_iterations=3
        )

        # Check iteration info is present
        assert "2/3" in message
        assert "Refinement attempt" in message

    def test_default_iteration_values(self):
        """Test default iteration values (1/3)."""
        result = CriticResult(score=0.3, message="Low score")
        message = build_refinement_message(result, threshold=0.5)

        # Check default iteration info
        assert "1/3" in message

    def test_custom_max_iterations(self):
        """Test custom max iterations value."""
        result = CriticResult(score=0.3, message="Low score")
        message = build_refinement_message(
            result, threshold=0.5, iteration=1, max_iterations=5
        )

        assert "1/5" in message


class TestRefinementIntegration:
    """Integration tests for iterative refinement behavior in the visualizer."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock app with conversation_manager and call_from_thread."""
        app = MagicMock(spec=App)
        app.conversation_id = "test-conv-123"
        app.conversation_manager = MagicMock()
        app.conversation_manager.post_message = MagicMock()
        app.call_from_thread = MagicMock()
        # Add conversation_state with agent_model for critic tracking
        app.conversation_state = MagicMock()
        app.conversation_state.agent_model = "openai/gpt-4o"
        return app

    @pytest.fixture
    def container(self):
        """Create a VerticalScroll container."""
        return VerticalScroll()

    def test_low_critic_score_triggers_refinement_message(
        self, mock_app, container, monkeypatch
    ):
        """Test that low critic scores trigger refinement messages.

        This integration test verifies that when:
        1. enable_iterative_refinement is True
        2. enable_critic is True
        3. A MessageEvent has a critic_result with score below threshold

        The visualizer will call _send_refinement_message, which posts a
        SendMessage to the ConversationManager.
        """
        # Set up CLI settings with refinement enabled
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=True,
                enable_iterative_refinement=True,
                critic_threshold=0.6,  # 60%
            )
        )
        monkeypatch.setattr(CliSettings, "load", lambda: settings)

        visualizer = ConversationVisualizer(
            container,
            mock_app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )
        # Clear any cached settings so it reloads with our mock
        visualizer._cli_settings = None

        # Create an agent message event with low critic score (below 60%)
        message = Message(
            role="assistant",
            content=[TextContent(text="I completed the task")],
        )
        event = MessageEvent(llm_message=message, source="agent")
        event = event.model_copy(
            update={
                "critic_result": CriticResult(
                    score=0.3,  # 30% - below 60% threshold
                    message="Low success probability",
                )
            }
        )

        # Mock _run_on_main_thread to avoid threading issues in tests
        visualizer._run_on_main_thread = MagicMock()

        # Process the event
        visualizer.on_event(event)

        # Verify that call_from_thread was called to send refinement message
        # Find the call that posts a SendMessage
        calls = mock_app.call_from_thread.call_args_list
        send_message_calls = [
            c
            for c in calls
            if len(c[0]) >= 2
            and hasattr(c[0][1], "__class__")
            and c[0][1].__class__.__name__ == "SendMessage"
        ]

        assert len(send_message_calls) == 1, (
            "Expected exactly one SendMessage call for refinement, "
            f"got {len(send_message_calls)}"
        )

        # Verify the message content mentions the score
        send_message = send_message_calls[0][0][1]
        assert "30.0%" in send_message.content, (
            f"Refinement message should contain the score percentage, "
            f"got: {send_message.content[:100]}..."
        )

    def test_high_critic_score_does_not_trigger_refinement(
        self, mock_app, container, monkeypatch
    ):
        """Test that high critic scores do NOT trigger refinement messages."""
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=True,
                enable_iterative_refinement=True,
                critic_threshold=0.6,
            )
        )
        monkeypatch.setattr(CliSettings, "load", lambda: settings)

        visualizer = ConversationVisualizer(
            container,
            mock_app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )
        visualizer._cli_settings = None

        # Create event with high critic score (above 60%)
        message = Message(
            role="assistant",
            content=[TextContent(text="Task completed")],
        )
        event = MessageEvent(llm_message=message, source="agent")
        event = event.model_copy(
            update={
                "critic_result": CriticResult(
                    score=0.8,  # 80% - above threshold
                    message="High success probability",
                )
            }
        )

        visualizer._run_on_main_thread = MagicMock()
        visualizer.on_event(event)

        # Verify no SendMessage was posted
        calls = mock_app.call_from_thread.call_args_list
        send_message_calls = [
            c
            for c in calls
            if len(c[0]) >= 2
            and hasattr(c[0][1], "__class__")
            and c[0][1].__class__.__name__ == "SendMessage"
        ]

        assert len(send_message_calls) == 0, (
            "No SendMessage should be posted for high critic scores"
        )

    def test_refinement_disabled_does_not_trigger(
        self, mock_app, container, monkeypatch
    ):
        """Test that refinement is not triggered when disabled in settings."""
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=True,
                enable_iterative_refinement=False,  # Disabled
                critic_threshold=0.6,
            )
        )
        monkeypatch.setattr(CliSettings, "load", lambda: settings)

        visualizer = ConversationVisualizer(
            container,
            mock_app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )
        visualizer._cli_settings = None

        # Low score that would trigger refinement if enabled
        message = Message(
            role="assistant",
            content=[TextContent(text="Task completed")],
        )
        event = MessageEvent(llm_message=message, source="agent")
        event = event.model_copy(
            update={
                "critic_result": CriticResult(
                    score=0.2,  # Very low
                    message="Low score",
                )
            }
        )

        visualizer._run_on_main_thread = MagicMock()
        visualizer.on_event(event)

        # Verify no SendMessage was posted
        calls = mock_app.call_from_thread.call_args_list
        send_message_calls = [
            c
            for c in calls
            if len(c[0]) >= 2
            and hasattr(c[0][1], "__class__")
            and c[0][1].__class__.__name__ == "SendMessage"
        ]

        assert len(send_message_calls) == 0, (
            "No SendMessage should be posted when refinement is disabled"
        )

    def test_critic_disabled_does_not_trigger(self, mock_app, container, monkeypatch):
        """Test that refinement is not triggered when critic is disabled."""
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=False,  # Critic disabled
                enable_iterative_refinement=True,
                critic_threshold=0.6,
            )
        )
        monkeypatch.setattr(CliSettings, "load", lambda: settings)

        visualizer = ConversationVisualizer(
            container,
            mock_app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )
        visualizer._cli_settings = None

        message = Message(
            role="assistant",
            content=[TextContent(text="Task completed")],
        )
        event = MessageEvent(llm_message=message, source="agent")
        event = event.model_copy(
            update={
                "critic_result": CriticResult(
                    score=0.2,
                    message="Low score",
                )
            }
        )

        visualizer._run_on_main_thread = MagicMock()
        visualizer.on_event(event)

        # Verify no SendMessage was posted (critic disabled = no critic processing)
        calls = mock_app.call_from_thread.call_args_list
        send_message_calls = [
            c
            for c in calls
            if len(c[0]) >= 2
            and hasattr(c[0][1], "__class__")
            and c[0][1].__class__.__name__ == "SendMessage"
        ]

        assert len(send_message_calls) == 0, (
            "No SendMessage should be posted when critic is disabled"
        )

    def test_refinement_max_iterations_limit(self, mock_app, container, monkeypatch):
        """Test that refinement stops after max iterations.

        With max_refinement_iterations=3 (default), the agent should receive
        at most 3 refinement messages before the loop stops.
        """
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=True,
                enable_iterative_refinement=True,
                critic_threshold=0.6,
                max_refinement_iterations=3,
            )
        )
        monkeypatch.setattr(CliSettings, "load", lambda: settings)

        visualizer = ConversationVisualizer(
            container,
            mock_app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )
        visualizer._cli_settings = None
        visualizer._run_on_main_thread = MagicMock()

        def create_low_score_event(text: str):
            message = Message(
                role="assistant",
                content=[TextContent(text=text)],
            )
            event = MessageEvent(llm_message=message, source="agent")
            return event.model_copy(
                update={
                    "critic_result": CriticResult(
                        score=0.3,  # Low score
                        message="Low score",
                    )
                }
            )

        # First 3 responses should all trigger refinement
        for i in range(3):
            mock_app.call_from_thread.reset_mock()
            visualizer.on_event(create_low_score_event(f"Response {i + 1}"))

            calls = mock_app.call_from_thread.call_args_list
            send_message_calls = [
                c
                for c in calls
                if len(c[0]) >= 2
                and hasattr(c[0][1], "__class__")
                and c[0][1].__class__.__name__ == "SendMessage"
            ]
            assert len(send_message_calls) == 1, (
                f"Response {i + 1} should trigger refinement (iteration {i + 1}/3)"
            )

        # Verify iteration counter is at max
        assert visualizer._refinement_iteration == 3

        # 4th response should NOT trigger refinement (max reached)
        mock_app.call_from_thread.reset_mock()
        visualizer.on_event(create_low_score_event("Response 4"))

        calls = mock_app.call_from_thread.call_args_list
        send_message_calls = [
            c
            for c in calls
            if len(c[0]) >= 2
            and hasattr(c[0][1], "__class__")
            and c[0][1].__class__.__name__ == "SendMessage"
        ]
        assert len(send_message_calls) == 0, (
            "4th response should NOT trigger refinement (max iterations reached)"
        )

    def test_refinement_custom_max_iterations(self, mock_app, container, monkeypatch):
        """Test that custom max_refinement_iterations is respected."""
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=True,
                enable_iterative_refinement=True,
                critic_threshold=0.6,
                max_refinement_iterations=1,  # Only 1 iteration allowed
            )
        )
        monkeypatch.setattr(CliSettings, "load", lambda: settings)

        visualizer = ConversationVisualizer(
            container,
            mock_app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )
        visualizer._cli_settings = None
        visualizer._run_on_main_thread = MagicMock()

        def create_low_score_event(text: str):
            message = Message(
                role="assistant",
                content=[TextContent(text=text)],
            )
            event = MessageEvent(llm_message=message, source="agent")
            return event.model_copy(
                update={
                    "critic_result": CriticResult(
                        score=0.3,
                        message="Low score",
                    )
                }
            )

        # First response should trigger refinement
        visualizer.on_event(create_low_score_event("First response"))
        calls1 = mock_app.call_from_thread.call_args_list
        send_message_calls1 = [
            c
            for c in calls1
            if len(c[0]) >= 2
            and hasattr(c[0][1], "__class__")
            and c[0][1].__class__.__name__ == "SendMessage"
        ]
        assert len(send_message_calls1) == 1, "First response should trigger refinement"

        # Clear and check second response doesn't trigger (max=1)
        mock_app.call_from_thread.reset_mock()
        visualizer.on_event(create_low_score_event("Second response"))

        calls2 = mock_app.call_from_thread.call_args_list
        send_message_calls2 = [
            c
            for c in calls2
            if len(c[0]) >= 2
            and hasattr(c[0][1], "__class__")
            and c[0][1].__class__.__name__ == "SendMessage"
        ]
        assert len(send_message_calls2) == 0, (
            "Second response should NOT trigger refinement (max=1 reached)"
        )

    def test_refinement_resets_on_user_message(self, mock_app, container, monkeypatch):
        """Test that refinement counter resets after user sends a message."""
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=True,
                enable_iterative_refinement=True,
                critic_threshold=0.6,
                max_refinement_iterations=2,  # Use small number for testing
            )
        )
        monkeypatch.setattr(CliSettings, "load", lambda: settings)

        visualizer = ConversationVisualizer(
            container,
            mock_app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )
        visualizer._cli_settings = None
        visualizer._run_on_main_thread = MagicMock()

        def create_low_score_event(text: str):
            message = Message(
                role="assistant",
                content=[TextContent(text=text)],
            )
            event = MessageEvent(llm_message=message, source="agent")
            return event.model_copy(
                update={
                    "critic_result": CriticResult(
                        score=0.3,
                        message="Low score",
                    )
                }
            )

        # Exhaust refinement iterations
        visualizer.on_event(create_low_score_event("First response"))
        visualizer.on_event(create_low_score_event("Second response"))

        # Should have reached max iterations
        assert visualizer._refinement_iteration == 2

        # User sends a new message (resets the counter)
        visualizer.render_user_message("Please try again with a different approach")

        # Counter should be reset
        assert visualizer._refinement_iteration == 0

        # Clear call history
        mock_app.call_from_thread.reset_mock()

        # Another agent response with low score
        visualizer.on_event(create_low_score_event("New attempt"))

        # Should trigger refinement again (new user turn, counter reset)
        calls = mock_app.call_from_thread.call_args_list
        send_message_calls = [
            c
            for c in calls
            if len(c[0]) >= 2
            and hasattr(c[0][1], "__class__")
            and c[0][1].__class__.__name__ == "SendMessage"
        ]
        assert len(send_message_calls) == 1, (
            "After user message, refinement should trigger again"
        )
        assert visualizer._refinement_iteration == 1
