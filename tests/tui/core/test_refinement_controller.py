"""Tests for RefinementController."""

from unittest.mock import MagicMock

import pytest

from openhands.sdk.critic.result import CriticResult
from openhands_cli.stores import CriticSettings
from openhands_cli.tui.core.refinement_controller import RefinementController
from openhands_cli.tui.messages import SendRefinementMessage


class TestRefinementController:
    """Tests for RefinementController."""

    @pytest.fixture
    def mock_state(self):
        """Create a mock ConversationContainer with critic settings."""
        state = MagicMock()
        state.critic_settings = CriticSettings(
            enable_critic=True,
            enable_iterative_refinement=True,
            critic_threshold=0.6,
            max_refinement_iterations=3,
            issue_threshold=0.75,
        )
        state.refinement_iteration = 0
        return state

    @pytest.fixture
    def mock_runners(self):
        """Create a mock RunnerRegistry."""
        return MagicMock()

    @pytest.fixture
    def mock_post_message(self):
        """Create a mock post_message function."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_state, mock_runners, mock_post_message):
        """Create a RefinementController with mocked dependencies."""
        return RefinementController(
            state=mock_state,
            runners=mock_runners,
            post_message=mock_post_message,
        )

    def test_low_score_triggers_refinement(
        self, controller, mock_state, mock_post_message
    ):
        """Low critic score should trigger refinement message."""
        result = CriticResult(score=0.3, message="Low score")

        controller.handle_critic_result(result)

        # Should increment iteration
        mock_state.set_refinement_iteration.assert_called_once_with(1)

        # Should post refinement message
        assert mock_post_message.call_count == 1
        call_args = mock_post_message.call_args[0][0]
        assert isinstance(call_args, SendRefinementMessage)
        assert "30.0%" in call_args.content

    def test_high_score_does_not_trigger_refinement(
        self, controller, mock_state, mock_post_message
    ):
        """High critic score should not trigger refinement."""
        result = CriticResult(score=0.8, message="Good score")

        controller.handle_critic_result(result)

        # Should not increment iteration
        mock_state.set_refinement_iteration.assert_not_called()

        # Should not post any message
        mock_post_message.assert_not_called()

    def test_refinement_disabled_does_not_trigger(
        self, mock_state, mock_runners, mock_post_message
    ):
        """When refinement is disabled, should not trigger."""
        mock_state.critic_settings = CriticSettings(
            enable_critic=True,
            enable_iterative_refinement=False,  # Disabled
            critic_threshold=0.6,
        )

        controller = RefinementController(
            state=mock_state,
            runners=mock_runners,
            post_message=mock_post_message,
        )

        result = CriticResult(score=0.2, message="Very low score")
        controller.handle_critic_result(result)

        mock_state.set_refinement_iteration.assert_not_called()
        mock_post_message.assert_not_called()

    def test_max_iterations_respected(
        self, mock_state, mock_runners, mock_post_message
    ):
        """Should not trigger when max iterations reached."""
        mock_state.critic_settings = CriticSettings(
            enable_critic=True,
            enable_iterative_refinement=True,
            critic_threshold=0.6,
            max_refinement_iterations=3,
        )
        # Already at max iterations
        mock_state.refinement_iteration = 3

        controller = RefinementController(
            state=mock_state,
            runners=mock_runners,
            post_message=mock_post_message,
        )

        result = CriticResult(score=0.2, message="Low score")
        controller.handle_critic_result(result)

        mock_state.set_refinement_iteration.assert_not_called()
        mock_post_message.assert_not_called()

    def test_iteration_counter_increments(
        self, mock_state, mock_runners, mock_post_message
    ):
        """Iteration counter should increment with each refinement."""
        mock_state.critic_settings = CriticSettings(
            enable_iterative_refinement=True,
            critic_threshold=0.6,
            max_refinement_iterations=5,
        )

        controller = RefinementController(
            state=mock_state,
            runners=mock_runners,
            post_message=mock_post_message,
        )

        result = CriticResult(score=0.3, message="Low score")

        # First iteration
        mock_state.refinement_iteration = 0
        controller.handle_critic_result(result)
        mock_state.set_refinement_iteration.assert_called_with(1)

        # Second iteration
        mock_state.refinement_iteration = 1
        mock_state.set_refinement_iteration.reset_mock()
        controller.handle_critic_result(result)
        mock_state.set_refinement_iteration.assert_called_with(2)

        # Third iteration
        mock_state.refinement_iteration = 2
        mock_state.set_refinement_iteration.reset_mock()
        controller.handle_critic_result(result)
        mock_state.set_refinement_iteration.assert_called_with(3)

    def test_reset_iteration(self, controller, mock_state):
        """reset_iteration should set counter to 0."""
        mock_state.refinement_iteration = 3

        controller.reset_iteration()

        mock_state.set_refinement_iteration.assert_called_once_with(0)

    def test_high_probability_issue_triggers_refinement(
        self, mock_state, mock_runners, mock_post_message
    ):
        """High-probability issue should trigger refinement even with good score."""
        mock_state.critic_settings = CriticSettings(
            enable_iterative_refinement=True,
            critic_threshold=0.5,
            issue_threshold=0.75,
            max_refinement_iterations=3,
        )
        mock_state.refinement_iteration = 0

        controller = RefinementController(
            state=mock_state,
            runners=mock_runners,
            post_message=mock_post_message,
        )

        # High score BUT with a high-probability issue
        result = CriticResult(
            score=0.8,  # Above threshold
            message="Good score but issue detected",
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

        controller.handle_critic_result(result)

        # Should trigger refinement due to high-probability issue
        mock_state.set_refinement_iteration.assert_called_once_with(1)
        assert mock_post_message.call_count == 1

        # Message should mention the issue
        message = mock_post_message.call_args[0][0]
        assert "Insufficient Testing" in message.content

    def test_issue_below_threshold_does_not_trigger(
        self, mock_state, mock_runners, mock_post_message
    ):
        """Issues below threshold should not trigger when score is good."""
        mock_state.critic_settings = CriticSettings(
            enable_iterative_refinement=True,
            critic_threshold=0.5,
            issue_threshold=0.75,
            max_refinement_iterations=3,
        )
        mock_state.refinement_iteration = 0

        controller = RefinementController(
            state=mock_state,
            runners=mock_runners,
            post_message=mock_post_message,
        )

        # Good score with issue below threshold
        result = CriticResult(
            score=0.8,
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

        controller.handle_critic_result(result)

        # Should not trigger
        mock_state.set_refinement_iteration.assert_not_called()
        mock_post_message.assert_not_called()

    def test_custom_max_iterations(self, mock_state, mock_runners, mock_post_message):
        """Custom max_refinement_iterations should be respected."""
        mock_state.critic_settings = CriticSettings(
            enable_iterative_refinement=True,
            critic_threshold=0.6,
            max_refinement_iterations=1,  # Only 1 iteration allowed
        )
        mock_state.refinement_iteration = 0

        controller = RefinementController(
            state=mock_state,
            runners=mock_runners,
            post_message=mock_post_message,
        )

        result = CriticResult(score=0.3, message="Low score")

        # First call should work
        controller.handle_critic_result(result)
        assert mock_state.set_refinement_iteration.call_count == 1
        assert mock_post_message.call_count == 1

        # Set iteration to 1 (max reached)
        mock_state.refinement_iteration = 1
        mock_state.set_refinement_iteration.reset_mock()
        mock_post_message.reset_mock()

        # Second call should not trigger (max reached)
        controller.handle_critic_result(result)
        mock_state.set_refinement_iteration.assert_not_called()
        mock_post_message.assert_not_called()

    def test_refinement_message_includes_iteration_info(
        self, controller, mock_state, mock_post_message
    ):
        """Refinement message should include iteration and max info."""
        mock_state.critic_settings = CriticSettings(
            enable_iterative_refinement=True,
            critic_threshold=0.6,
            max_refinement_iterations=5,
        )
        mock_state.refinement_iteration = 2

        result = CriticResult(score=0.3, message="Low score")
        controller.handle_critic_result(result)

        message = mock_post_message.call_args[0][0]
        # Should show "iteration 3/5" (since we're going from 2 to 3)
        assert "iteration 3/5" in message.content
