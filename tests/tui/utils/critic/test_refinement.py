"""Tests for the iterative refinement utilities."""

from unittest.mock import MagicMock

import pytest
from textual.app import App
from textual.containers import VerticalScroll

from openhands.sdk import Message, TextContent
from openhands.sdk.critic.result import CriticResult
from openhands.sdk.event import MessageEvent
from openhands_cli.stores import CliSettings, CriticSettings
from openhands_cli.tui.core.conversation_manager import (
    CriticResultReceived,
)
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


class TestVisualizerCriticResultHandling:
    """Tests for visualizer's handling of critic results.

    With the RefinementController refactoring, the visualizer is now only
    responsible for:
    1. Displaying critic widgets (collapsible, feedback)
    2. Posting CriticResultReceived messages for the controller to handle

    Refinement logic tests are in tests/tui/core/test_refinement_controller.py
    """

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

    def test_critic_result_posts_message_to_controller(
        self, mock_app, container, monkeypatch
    ):
        """Test that critic results are posted to ConversationManager.

        The visualizer should post CriticResultReceived for the
        RefinementController to evaluate and handle.
        """
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
        visualizer._run_on_main_thread = MagicMock()

        # Create an agent message event with critic result
        critic_result = CriticResult(
            score=0.3,
            message="Low success probability",
        )
        message = Message(
            role="assistant",
            content=[TextContent(text="I completed the task")],
        )
        event = MessageEvent(llm_message=message, source="agent")
        event = event.model_copy(update={"critic_result": critic_result})

        visualizer.on_event(event)

        # Verify that CriticResultReceived was posted
        calls = mock_app.call_from_thread.call_args_list
        critic_result_calls = [
            c
            for c in calls
            if len(c[0]) >= 2 and isinstance(c[0][1], CriticResultReceived)
        ]

        assert len(critic_result_calls) == 1, (
            "Expected exactly one CriticResultReceived message, "
            f"got {len(critic_result_calls)}"
        )

        # Verify the critic result was passed correctly
        posted_message = critic_result_calls[0][0][1]
        assert posted_message.critic_result.score == 0.3

    def test_critic_disabled_does_not_post_message(
        self, mock_app, container, monkeypatch
    ):
        """Test that no message is posted when critic is disabled."""
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=False,  # Disabled
                enable_iterative_refinement=True,
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

        visualizer.on_event(event)

        # No CriticResultReceived should be posted when critic is disabled
        calls = mock_app.call_from_thread.call_args_list
        critic_result_calls = [
            c
            for c in calls
            if len(c[0]) >= 2 and isinstance(c[0][1], CriticResultReceived)
        ]

        assert len(critic_result_calls) == 0, (
            "No CriticResultReceived should be posted when critic is disabled"
        )

    def test_event_without_critic_result_does_not_post(
        self, mock_app, container, monkeypatch
    ):
        """Test that events without critic results don't post messages."""
        settings = CliSettings(
            critic=CriticSettings(
                enable_critic=True,
                enable_iterative_refinement=True,
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

        # Event WITHOUT critic_result
        message = Message(
            role="assistant",
            content=[TextContent(text="Task completed")],
        )
        event = MessageEvent(llm_message=message, source="agent")

        visualizer.on_event(event)

        # No CriticResultReceived should be posted
        calls = mock_app.call_from_thread.call_args_list
        critic_result_calls = [
            c
            for c in calls
            if len(c[0]) >= 2 and isinstance(c[0][1], CriticResultReceived)
        ]

        assert len(critic_result_calls) == 0

    def test_render_user_message_dismisses_feedback_widgets(
        self, mock_app, container, monkeypatch
    ):
        """Test that render_user_message dismisses pending feedback widgets."""
        settings = CliSettings(critic=CriticSettings(enable_critic=True))
        monkeypatch.setattr(CliSettings, "load", lambda: settings)

        visualizer = ConversationVisualizer(
            container,
            mock_app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )
        visualizer._cli_settings = None
        visualizer._run_on_main_thread = MagicMock()

        # render_user_message should not raise an error
        visualizer.render_user_message("Hello")

        # Verify the message was rendered (by checking _run_on_main_thread was called)
        assert visualizer._run_on_main_thread.called

    def test_render_refinement_message_dismisses_feedback_widgets(
        self, mock_app, container, monkeypatch
    ):
        """Test that render_refinement_message dismisses pending feedback widgets."""
        settings = CliSettings(critic=CriticSettings(enable_critic=True))
        monkeypatch.setattr(CliSettings, "load", lambda: settings)

        visualizer = ConversationVisualizer(
            container,
            mock_app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )
        visualizer._cli_settings = None
        visualizer._run_on_main_thread = MagicMock()

        # render_refinement_message should not raise an error
        visualizer.render_refinement_message("Refinement needed")

        # Verify the message was rendered
        assert visualizer._run_on_main_thread.called
