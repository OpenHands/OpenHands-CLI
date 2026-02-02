"""Tests for the iterative refinement utilities."""

from openhands.sdk.critic.result import CriticResult
from openhands_cli.tui.utils.critic.refinement import (
    build_refinement_message,
    should_trigger_refinement,
)


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

        # Check header
        assert "Iterative Refinement Triggered" in message

        # Check score mentioned
        assert "30.0%" in message

        # Check threshold mentioned
        assert "50%" in message

        # Check instruction to review
        assert "Please review the user's original requirements" in message

    def test_includes_categorized_features(self):
        """Test that categorized features from metadata are included."""
        categorized = {
            "agent_behavioral_issues": [
                {"display_name": "Incomplete Task", "probability": 0.8},
                {"display_name": "Missing Tests", "probability": 0.6},
            ],
            "infrastructure_issues": [
                {"display_name": "Build Failed", "probability": 0.7},
            ],
        }
        result = CriticResult(
            score=0.4,
            message="Issues detected",
            metadata={"categorized_features": categorized},
        )
        message = build_refinement_message(result, threshold=0.5)

        # Check that issues are mentioned
        assert "Incomplete Task" in message
        assert "80%" in message
        assert "Missing Tests" in message
        assert "60%" in message
        assert "Build Failed" in message
        assert "70%" in message

    def test_includes_user_followup_patterns(self):
        """Test that user followup patterns are included if present."""
        categorized = {
            "user_followup_patterns": [
                {"display_name": "Clarification Needed", "probability": 0.9},
            ],
        }
        result = CriticResult(
            score=0.3,
            message="Follow-up needed",
            metadata={"categorized_features": categorized},
        )
        message = build_refinement_message(result, threshold=0.5)

        assert "Clarification Needed" in message
        assert "90%" in message

    def test_handles_missing_categorized_features(self):
        """Test that message works without categorized features."""
        result = CriticResult(score=0.3, message="Simple message")
        message = build_refinement_message(result, threshold=0.5)

        # Should still have basic structure
        assert "Iterative Refinement Triggered" in message
        assert "30.0%" in message

        # Should not crash and should include instructions
        assert "Please review" in message

    def test_handles_empty_categorized_features(self):
        """Test that message works with empty categorized features."""
        result = CriticResult(
            score=0.3,
            message="Empty features",
            metadata={"categorized_features": {}},
        )
        message = build_refinement_message(result, threshold=0.5)

        # Should still have basic structure without crashing
        assert "Iterative Refinement Triggered" in message

    def test_feature_uses_name_fallback(self):
        """Test that 'name' is used as fallback when 'display_name' is missing."""
        categorized = {
            "agent_behavioral_issues": [
                {"name": "raw_feature_name", "probability": 0.7},
            ],
        }
        result = CriticResult(
            score=0.3,
            message="Feature name fallback",
            metadata={"categorized_features": categorized},
        )
        message = build_refinement_message(result, threshold=0.5)

        assert "raw_feature_name" in message

    def test_threshold_formatting(self):
        """Test various threshold values are formatted correctly."""
        result = CriticResult(score=0.2, message="Test")

        # Test decimal threshold
        message = build_refinement_message(result, threshold=0.75)
        assert "75%" in message

        # Test integer-like threshold
        message = build_refinement_message(result, threshold=1.0)
        assert "100%" in message


class TestDefaultCriticThreshold:
    """Tests for DEFAULT_CRITIC_THRESHOLD constant."""

    def test_default_threshold_value(self):
        """Test that the default critic threshold is 0.5."""
        from openhands_cli.argparsers.util import DEFAULT_CRITIC_THRESHOLD

        assert DEFAULT_CRITIC_THRESHOLD == 0.5

    def test_threshold_used_in_should_trigger_refinement(self):
        """Test that DEFAULT_CRITIC_THRESHOLD works with should_trigger_refinement."""
        from openhands_cli.argparsers.util import DEFAULT_CRITIC_THRESHOLD

        # Score below default threshold
        result = CriticResult(score=0.3, message="Below threshold")
        assert (
            should_trigger_refinement(
                result, threshold=DEFAULT_CRITIC_THRESHOLD, enabled=True
            )
            is True
        )

        # Score above default threshold
        result = CriticResult(score=0.7, message="Above threshold")
        assert (
            should_trigger_refinement(
                result, threshold=DEFAULT_CRITIC_THRESHOLD, enabled=True
            )
            is False
        )
