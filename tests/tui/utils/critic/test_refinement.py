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
        # Should have score line, empty line, instruction, and numbered steps
        assert len(lines) <= 10


class TestDefaultCriticThreshold:
    """Tests for DEFAULT_CRITIC_THRESHOLD constant."""

    def test_default_threshold_value(self):
        """Test that the default critic threshold is 0.6 (same as SDK default)."""
        from openhands_cli.stores.cli_settings import DEFAULT_CRITIC_THRESHOLD

        assert DEFAULT_CRITIC_THRESHOLD == 0.6

    def test_threshold_used_in_should_trigger_refinement(self):
        """Test that DEFAULT_CRITIC_THRESHOLD works with should_trigger_refinement."""
        from openhands_cli.stores.cli_settings import DEFAULT_CRITIC_THRESHOLD

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
