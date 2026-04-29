"""Tests for critic refinement behavior used by the CLI."""

from unittest.mock import MagicMock

import pytest
from textual.app import App
from textual.containers import VerticalScroll

from openhands.sdk import Message, TextContent
from openhands.sdk.critic.result import CriticResult
from openhands.sdk.event import MessageEvent
from openhands_cli.stores import CliProgrammaticSettings, CriticSettings
from openhands_cli.tui.core.conversation_manager import CriticResultReceived
from openhands_cli.tui.utils.critic.refinement import (
    build_refinement_message,
    evaluate_iterative_refinement,
    get_high_probability_issues,
)
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


class TestEvaluateIterativeRefinement:
    def test_none_result_does_not_refine(self) -> None:
        decision = evaluate_iterative_refinement(None, success_threshold=0.5)

        assert decision.should_refine is False
        assert decision.triggered_issues == ()

    def test_low_score_triggers_refinement(self) -> None:
        result = CriticResult(score=0.3, message="Low score")

        decision = evaluate_iterative_refinement(result, success_threshold=0.5)

        assert decision.should_refine is True
        assert decision.triggered_issues == ()

    def test_high_probability_issue_triggers_refinement(self) -> None:
        result = CriticResult(
            score=0.8,
            message="Good score but has issue",
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

        decision = evaluate_iterative_refinement(
            result,
            success_threshold=0.5,
            issue_threshold=0.75,
        )

        assert decision.should_refine is True
        assert decision.triggered_issues[0]["name"] == "insufficient_testing"


class TestGetHighProbabilityIssues:
    def test_filters_and_sorts_issues(self) -> None:
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
                            "probability": 0.50,
                        },
                    ]
                }
            },
        )

        issues = get_high_probability_issues(result, issue_threshold=0.75)

        assert [issue["name"] for issue in issues] == [
            "loop_behavior",
            "insufficient_testing",
        ]


class TestBuildRefinementMessage:
    def test_basic_message_structure(self) -> None:
        result = CriticResult(score=0.3, message="Low score")

        message = build_refinement_message(result, iteration=1, max_iterations=3)

        assert "30.0%" in message
        assert "iteration 1/3" in message
        assert "The task appears incomplete" in message
        assert "Please review what you've done" in message

    def test_message_includes_triggered_issues(self) -> None:
        result = CriticResult(score=0.8, message="Good score but has issues")

        message = build_refinement_message(
            result,
            iteration=1,
            max_iterations=3,
            triggered_issues=(
                {
                    "name": "insufficient_testing",
                    "display_name": "Insufficient Testing",
                    "probability": 0.80,
                },
            ),
        )

        assert "Detected issues requiring attention" in message
        assert "Insufficient Testing (80%)" in message

    def test_message_extracts_issues_from_metadata(self) -> None:
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
            iteration=1,
            max_iterations=3,
            issue_threshold=0.75,
        )

        assert "Detected issues requiring attention" in message
        assert "Insufficient Testing (80%)" in message

    def test_message_is_concise_without_issues(self) -> None:
        result = CriticResult(score=0.4, message="Test")

        message = build_refinement_message(result, iteration=1, max_iterations=3)

        assert len(message.strip().split("\n")) <= 6


class TestVisualizerCriticResultHandling:
    @pytest.fixture
    def mock_app(self):
        app = MagicMock(spec=App)
        app.conversation_id = "test-conv-123"
        app.conversation_manager = MagicMock()
        app.conversation_manager.post_message = MagicMock()
        app.call_from_thread = MagicMock()
        app.conversation_state = MagicMock()
        app.conversation_state.agent_model = "openai/gpt-4o"
        return app

    @pytest.fixture
    def container(self):
        return VerticalScroll()

    def test_critic_result_posts_message_to_controller(
        self, mock_app, container, monkeypatch
    ) -> None:
        settings = CliProgrammaticSettings(
            verification=CriticSettings(
                critic_enabled=True,
                enable_iterative_refinement=True,
                critic_threshold=0.6,
            )
        )
        monkeypatch.setattr(CliProgrammaticSettings, "load", lambda: settings)

        visualizer = ConversationVisualizer(
            container,
            mock_app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )
        visualizer._cli_settings = None
        visualizer._run_on_main_thread = MagicMock()

        critic_result = CriticResult(score=0.3, message="Low success probability")
        message = Message(
            role="assistant",
            content=[TextContent(text="I completed the task")],
        )
        event = MessageEvent(llm_message=message, source="agent")
        event = event.model_copy(update={"critic_result": critic_result})

        visualizer.on_event(event)

        calls = mock_app.call_from_thread.call_args_list
        critic_result_calls = [
            c
            for c in calls
            if len(c[0]) >= 2 and isinstance(c[0][1], CriticResultReceived)
        ]

        assert len(critic_result_calls) == 1
        posted_message = critic_result_calls[0][0][1]
        assert posted_message.critic_result.score == 0.3

    def test_critic_disabled_does_not_post_message(
        self, mock_app, container, monkeypatch
    ) -> None:
        settings = CliProgrammaticSettings(
            verification=CriticSettings(
                critic_enabled=False,
                enable_iterative_refinement=True,
            )
        )
        monkeypatch.setattr(CliProgrammaticSettings, "load", lambda: settings)

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

        calls = mock_app.call_from_thread.call_args_list
        critic_result_calls = [
            c
            for c in calls
            if len(c[0]) >= 2 and isinstance(c[0][1], CriticResultReceived)
        ]

        assert len(critic_result_calls) == 0

    def test_event_without_critic_result_does_not_post(
        self, mock_app, container, monkeypatch
    ) -> None:
        settings = CliProgrammaticSettings(
            verification=CriticSettings(
                critic_enabled=True,
                enable_iterative_refinement=True,
            )
        )
        monkeypatch.setattr(CliProgrammaticSettings, "load", lambda: settings)

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

        visualizer.on_event(event)

        calls = mock_app.call_from_thread.call_args_list
        critic_result_calls = [
            c
            for c in calls
            if len(c[0]) >= 2 and isinstance(c[0][1], CriticResultReceived)
        ]

        assert len(critic_result_calls) == 0
