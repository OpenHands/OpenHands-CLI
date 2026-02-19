"""Tests for the iterative refinement utilities."""

from unittest.mock import MagicMock

import pytest
from textual.app import App
from textual.containers import VerticalScroll

from openhands.sdk import Message, TextContent
from openhands.sdk.critic.result import CriticResult
from openhands.sdk.event import MessageEvent
from openhands_cli.stores import CliSettings, CriticSettings
from openhands_cli.tui.core.conversation_manager import SendRefinementMessage
from openhands_cli.tui.utils.critic.refinement import (
    build_refinement_message,
    get_high_probability_issues,
    should_trigger_refinement,
)
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


class TestShouldTriggerRefinement:
    """Tests for should_trigger_refinement function."""

    def test_none_result_returns_false(self):
        """When critic result is None, should return False."""
        should_trigger, issues = should_trigger_refinement(None, threshold=0.5)
        assert not should_trigger
        assert issues == []

    def test_score_below_threshold_returns_true(self):
        """When score is below threshold, should return True."""
        result = CriticResult(score=0.3, message="Low score")
        should_trigger, _ = should_trigger_refinement(result, threshold=0.5)
        assert should_trigger

    def test_score_at_threshold_returns_false(self):
        """When score equals threshold, should return False (not below)."""
        result = CriticResult(score=0.5, message="At threshold")
        should_trigger, _ = should_trigger_refinement(result, threshold=0.5)
        assert not should_trigger

    def test_score_above_threshold_returns_false(self):
        """When score is above threshold, should return False."""
        result = CriticResult(score=0.8, message="Good score")
        should_trigger, _ = should_trigger_refinement(result, threshold=0.5)
        assert not should_trigger

    def test_custom_threshold(self):
        """Custom threshold should be respected."""
        result = CriticResult(score=0.6, message="Medium score")
        # Should NOT trigger with default threshold of 0.5
        should_trigger1, _ = should_trigger_refinement(result, threshold=0.5)
        assert not should_trigger1
        # Should trigger with higher threshold of 0.7
        should_trigger2, _ = should_trigger_refinement(result, threshold=0.7)
        assert should_trigger2

    def test_high_probability_issue_triggers_refinement(self):
        """When an issue has probability above issue_threshold, trigger refinement."""
        result = CriticResult(
            score=0.8,  # High score - would NOT trigger normally
            message="Good score but has issue",
            metadata={
                "categorized_features": {
                    "agent_behavioral_issues": [
                        {
                            "name": "insufficient_testing",
                            "display_name": "Insufficient Testing",
                            "probability": 0.80,  # Above 0.75 threshold
                        }
                    ]
                }
            },
        )
        should_trigger, issues = should_trigger_refinement(
            result, threshold=0.5, issue_threshold=0.75
        )
        assert should_trigger
        assert len(issues) == 1
        assert issues[0]["name"] == "insufficient_testing"

    def test_issue_below_threshold_does_not_trigger(self):
        """When issue probability is below issue_threshold, don't trigger."""
        result = CriticResult(
            score=0.8,  # High score
            message="Good score",
            metadata={
                "categorized_features": {
                    "agent_behavioral_issues": [
                        {
                            "name": "insufficient_testing",
                            "display_name": "Insufficient Testing",
                            "probability": 0.50,  # Below 0.75 threshold
                        }
                    ]
                }
            },
        )
        should_trigger, issues = should_trigger_refinement(
            result, threshold=0.5, issue_threshold=0.75
        )
        assert not should_trigger
        assert issues == []

    def test_multiple_high_probability_issues(self):
        """Multiple issues above threshold should all be returned."""
        result = CriticResult(
            score=0.8,
            message="Good score but has issues",
            metadata={
                "categorized_features": {
                    "agent_behavioral_issues": [
                        {
                            "name": "insufficient_testing",
                            "display_name": "Insufficient Testing",
                            "probability": 0.80,
                        },
                        {
                            "name": "loop_behavior",
                            "display_name": "Loop Behavior",
                            "probability": 0.85,
                        },
                        {
                            "name": "scope_creep",
                            "display_name": "Scope Creep",
                            "probability": 0.50,  # Below threshold
                        },
                    ]
                }
            },
        )
        should_trigger, issues = should_trigger_refinement(
            result, threshold=0.5, issue_threshold=0.75
        )
        assert should_trigger
        assert len(issues) == 2
        # Issues should be sorted by probability (highest first)
        assert issues[0]["name"] == "loop_behavior"
        assert issues[1]["name"] == "insufficient_testing"

    def test_infrastructure_issues_not_checked_for_refinement(self):
        """Infrastructure issues alone do not trigger refinement.

        The refinement logic only checks agent_behavioral_issues,
        not infrastructure_issues, since infrastructure issues are
        typically not actionable by agent refinement.
        """
        result = CriticResult(
            score=0.8,
            message="Good score but infra issue",
            metadata={
                "categorized_features": {
                    "agent_behavioral_issues": [],
                    "infrastructure_issues": [
                        {
                            "name": "infrastructure_agent_caused_issue",
                            "display_name": "Infrastructure Agent Caused Issue",
                            "probability": 0.90,
                        }
                    ],
                }
            },
        )
        should_trigger, issues = should_trigger_refinement(
            result, threshold=0.5, issue_threshold=0.75
        )
        # Infrastructure issues alone don't trigger refinement when score is good
        assert not should_trigger
        assert len(issues) == 0


class TestGetHighProbabilityIssues:
    """Tests for get_high_probability_issues function."""

    def test_no_metadata_returns_empty(self):
        """When there's no metadata, return empty list."""
        result = CriticResult(score=0.5, message="Test")
        issues = get_high_probability_issues(result, issue_threshold=0.75)
        assert issues == []

    def test_no_categorized_features_returns_empty(self):
        """When there are no categorized features, return empty list."""
        result = CriticResult(score=0.5, message="Test", metadata={})
        issues = get_high_probability_issues(result, issue_threshold=0.75)
        assert issues == []

    def test_filters_by_threshold(self):
        """Only issues at or above threshold should be returned."""
        result = CriticResult(
            score=0.5,
            message="Test",
            metadata={
                "categorized_features": {
                    "agent_behavioral_issues": [
                        {"name": "a", "probability": 0.80},
                        {"name": "b", "probability": 0.74},  # Just below
                        {"name": "c", "probability": 0.75},  # At threshold
                    ]
                }
            },
        )
        issues = get_high_probability_issues(result, issue_threshold=0.75)
        assert len(issues) == 2
        names = [i["name"] for i in issues]
        assert "a" in names
        assert "c" in names
        assert "b" not in names


class TestBuildRefinementMessage:
    """Tests for build_refinement_message function."""

    def test_basic_message_structure(self):
        """Test that message has expected structure and content (SDK format)."""
        result = CriticResult(score=0.3, message="Low score")
        message = build_refinement_message(result)

        # Check score mentioned (SDK format: "predicted success likelihood")
        assert "30.0%" in message

        # Check iteration format (SDK style: "iteration X/Y")
        assert "iteration 1/3" in message

        # Check the task appears incomplete message (SDK style)
        assert "The task appears incomplete" in message

        # Check instruction to review (SDK style)
        assert "Please review what you've done" in message

    def test_includes_review_instructions(self):
        """Test that message includes review instructions (SDK format)."""
        result = CriticResult(score=0.4, message="Issues detected")
        message = build_refinement_message(result)

        # Check for SDK-style review instructions
        assert "verify each requirement is met" in message
        assert "List what's working and what needs fixing" in message

    def test_handles_missing_metadata(self):
        """Test that message works without metadata."""
        result = CriticResult(score=0.3, message="Simple message")
        message = build_refinement_message(result)

        # Should still have basic structure
        assert "30.0%" in message
        assert "Please review" in message

    def test_score_formatting(self):
        """Test various score values are formatted correctly."""
        # Test low score
        result = CriticResult(score=0.2, message="Test")
        message = build_refinement_message(result)
        assert "20.0%" in message

        # Test higher score
        result = CriticResult(score=0.55, message="Test")
        message = build_refinement_message(result)
        assert "55.0%" in message

    def test_message_is_concise_without_issues(self):
        """Test that the message follows SDK pattern of being concise."""
        result = CriticResult(score=0.4, message="Test")
        message = build_refinement_message(result)

        # Message should be relatively short (SDK style is concise)
        lines = message.strip().split("\n")
        # Without issues, should have 5 lines max
        assert len(lines) <= 6

    def test_iteration_info_included(self):
        """Test that iteration info is included in the message."""
        result = CriticResult(score=0.3, message="Low score")
        message = build_refinement_message(result, iteration=2, max_iterations=3)

        # Check iteration info is present (SDK format: "iteration X/Y")
        assert "iteration 2/3" in message

    def test_default_iteration_values(self):
        """Test default iteration values (1/3)."""
        result = CriticResult(score=0.3, message="Low score")
        message = build_refinement_message(result)

        # Check default iteration info
        assert "iteration 1/3" in message

    def test_custom_max_iterations(self):
        """Test custom max iterations value."""
        result = CriticResult(score=0.3, message="Low score")
        message = build_refinement_message(result, iteration=1, max_iterations=5)

        assert "iteration 1/5" in message

    def test_message_includes_triggered_issues(self):
        """Test that triggered issues are included in the message."""
        result = CriticResult(
            score=0.8,
            message="Good score but has issues",
            metadata={
                "categorized_features": {
                    "agent_behavioral_issues": [
                        {
                            "name": "insufficient_testing",
                            "display_name": "Insufficient Testing",
                            "probability": 0.80,
                        }
                    ]
                }
            },
        )
        triggered_issues = [
            {
                "name": "insufficient_testing",
                "display_name": "Insufficient Testing",
                "probability": 0.80,
            }
        ]
        message = build_refinement_message(
            result,
            triggered_issues=triggered_issues,
        )

        assert "**Detected issues requiring attention:**" in message
        assert "Insufficient Testing (80%)" in message

    def test_message_extracts_issues_if_not_provided(self):
        """Test that issues are extracted from metadata if not provided."""
        result = CriticResult(
            score=0.8,
            message="Good score but has issues",
            metadata={
                "categorized_features": {
                    "agent_behavioral_issues": [
                        {
                            "name": "insufficient_testing",
                            "display_name": "Insufficient Testing",
                            "probability": 0.80,
                        }
                    ]
                }
            },
        )
        message = build_refinement_message(
            result,
            issue_threshold=0.75,
        )

        assert "**Detected issues requiring attention:**" in message
        assert "Insufficient Testing (80%)" in message

    def test_message_with_multiple_issues(self):
        """Test that multiple issues are all listed."""
        triggered_issues = [
            {
                "name": "loop_behavior",
                "display_name": "Loop Behavior",
                "probability": 0.85,
            },
            {
                "name": "insufficient_testing",
                "display_name": "Insufficient Testing",
                "probability": 0.80,
            },
        ]
        result = CriticResult(score=0.8, message="Test")
        message = build_refinement_message(
            result,
            triggered_issues=triggered_issues,
        )

        assert "Loop Behavior (85%)" in message
        assert "Insufficient Testing (80%)" in message


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
        SendRefinementMessage to the ConversationManager.
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
        # Find the call that posts a SendRefinementMessage
        calls = mock_app.call_from_thread.call_args_list
        send_message_calls = [
            c
            for c in calls
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
        ]

        assert len(send_message_calls) == 1, (
            "Expected exactly one SendRefinementMessage call for refinement, "
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
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
        ]

        assert len(send_message_calls) == 0, (
            "No SendRefinementMessage should be posted for high critic scores"
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
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
        ]

        assert len(send_message_calls) == 0, (
            "No SendRefinementMessage should be posted when refinement is disabled"
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
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
        ]

        assert len(send_message_calls) == 0, (
            "No SendRefinementMessage should be posted when critic is disabled"
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
                if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
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
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
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
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
        ]
        assert len(send_message_calls1) == 1, "First response should trigger refinement"

        # Clear and check second response doesn't trigger (max=1)
        mock_app.call_from_thread.reset_mock()
        visualizer.on_event(create_low_score_event("Second response"))

        calls2 = mock_app.call_from_thread.call_args_list
        send_message_calls2 = [
            c
            for c in calls2
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
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
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
        ]
        assert len(send_message_calls) == 1, (
            "After user message, refinement should trigger again"
        )
        assert visualizer._refinement_iteration == 1

    def test_refinement_message_does_not_reset_counter(
        self, mock_app, container, monkeypatch
    ):
        """Test that render_refinement_message() doesn't reset counter.

        This is crucial for correct iteration tracking: when a refinement message
        is sent via render_refinement_message(), it should NOT reset the iteration
        counter, unlike render_user_message() which starts a new user turn.
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
                        score=0.3,
                        message="Low score",
                    )
                }
            )

        # First iteration
        visualizer.on_event(create_low_score_event("First response"))
        assert visualizer._refinement_iteration == 1

        # Simulate a refinement message using the dedicated method
        # This should NOT reset the counter (unlike render_user_message)
        visualizer.render_refinement_message(
            "The task appears incomplete (iteration 1/3...)",
        )

        # Counter should still be 1 (not reset to 0)
        assert visualizer._refinement_iteration == 1, (
            "Refinement message should not reset the iteration counter"
        )

        # Second iteration (agent response to refinement message)
        visualizer.on_event(create_low_score_event("Second response"))
        assert visualizer._refinement_iteration == 2

        # Third iteration
        visualizer.on_event(create_low_score_event("Third response"))
        assert visualizer._refinement_iteration == 3

        # Fourth response should NOT increment (max reached)
        mock_app.call_from_thread.reset_mock()
        visualizer.on_event(create_low_score_event("Fourth response"))

        # Counter should still be 3 (hit max, no increment)
        assert visualizer._refinement_iteration == 3

        # No refinement message should be sent
        calls = mock_app.call_from_thread.call_args_list
        send_message_calls = [
            c
            for c in calls
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
        ]
        assert len(send_message_calls) == 0

    def test_high_probability_issue_triggers_refinement(
        self, mock_app, container, monkeypatch
    ):
        """Test that high-probability issues trigger refinement even with good score.

        When an issue (e.g., insufficient_testing) has probability >= issue_threshold,
        refinement should be triggered even if overall score is above critic_threshold.
        """
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=True,
                enable_iterative_refinement=True,
                critic_threshold=0.5,  # Overall score threshold
                issue_threshold=0.75,  # Issue detection threshold
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

        # Create event with HIGH overall score but a specific issue detected
        message = Message(
            role="assistant",
            content=[TextContent(text="Task completed")],
        )
        event = MessageEvent(llm_message=message, source="agent")
        event = event.model_copy(
            update={
                "critic_result": CriticResult(
                    score=0.8,  # 80% - ABOVE threshold
                    message="High success probability",
                    metadata={
                        "categorized_features": {
                            "agent_behavioral_issues": [
                                {
                                    "name": "insufficient_testing",
                                    "display_name": "Insufficient Testing",
                                    "probability": 0.80,  # Above 75% issue threshold
                                }
                            ]
                        }
                    },
                )
            }
        )

        visualizer.on_event(event)

        # Verify refinement WAS triggered due to high-probability issue
        calls = mock_app.call_from_thread.call_args_list
        send_message_calls = [
            c
            for c in calls
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
        ]

        assert len(send_message_calls) == 1, (
            "Refinement should be triggered for high-probability issue"
        )

        # Verify the message mentions the issue
        send_message = send_message_calls[0][0][1]
        assert "Insufficient Testing" in send_message.content, (
            f"Refinement message should mention the issue, "
            f"got: {send_message.content[:200]}..."
        )

    def test_issue_below_threshold_does_not_trigger(
        self, mock_app, container, monkeypatch
    ):
        """Test that issues below threshold don't trigger refinement."""
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=True,
                enable_iterative_refinement=True,
                critic_threshold=0.5,
                issue_threshold=0.75,  # High threshold
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

        # Create event with high score AND issue below threshold
        message = Message(
            role="assistant",
            content=[TextContent(text="Task completed")],
        )
        event = MessageEvent(llm_message=message, source="agent")
        event = event.model_copy(
            update={
                "critic_result": CriticResult(
                    score=0.8,  # High score
                    message="Good",
                    metadata={
                        "categorized_features": {
                            "agent_behavioral_issues": [
                                {
                                    "name": "insufficient_testing",
                                    "display_name": "Insufficient Testing",
                                    "probability": 0.50,  # BELOW 75% threshold
                                }
                            ]
                        }
                    },
                )
            }
        )

        visualizer.on_event(event)

        # Verify refinement was NOT triggered
        calls = mock_app.call_from_thread.call_args_list
        send_message_calls = [
            c
            for c in calls
            if len(c[0]) >= 2 and isinstance(c[0][1], SendRefinementMessage)
        ]

        assert len(send_message_calls) == 0, (
            "No refinement should be triggered when issue is below threshold"
        )
