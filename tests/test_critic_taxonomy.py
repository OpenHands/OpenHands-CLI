"""Tests for critic visualization using SDK taxonomy."""

from openhands.sdk.critic import (
    FEATURE_CATEGORIES,
    categorize_features,
    get_category,
)


def test_feature_categories_count():
    """Test that we have the expected number of features."""
    assert len(FEATURE_CATEGORIES) == 26


def test_general_context_features():
    """Test general context features."""
    assert get_category("user_goal_summary") == "general_context"
    assert get_category("overall_sentiment") == "general_context"


def test_agent_behavioral_issues():
    """Test agent behavioral issue features."""
    assert get_category("misunderstood_intention") == "agent_behavioral_issues"
    assert get_category("loop_behavior") == "agent_behavioral_issues"
    assert get_category("incomplete_implementation") == "agent_behavioral_issues"


def test_user_followup_patterns():
    """Test user follow-up pattern features."""
    assert get_category("follow_up_timing") == "user_followup_patterns"
    assert get_category("clarification_or_restatement") == "user_followup_patterns"
    assert get_category("correction") == "user_followup_patterns"


def test_infrastructure_issues():
    """Test infrastructure issue features."""
    assert get_category("infrastructure_external_issue") == "infrastructure_issues"
    assert get_category("infrastructure_agent_caused_issue") == "infrastructure_issues"


def test_unknown_feature():
    """Test that unknown features return None."""
    assert get_category("nonexistent_feature") is None


def test_category_counts():
    """Test that each category has the expected number of features."""
    general = [k for k, v in FEATURE_CATEGORIES.items() if v == "general_context"]
    agent = [k for k, v in FEATURE_CATEGORIES.items() if v == "agent_behavioral_issues"]
    user = [k for k, v in FEATURE_CATEGORIES.items() if v == "user_followup_patterns"]
    infra = [k for k, v in FEATURE_CATEGORIES.items() if v == "infrastructure_issues"]

    assert len(general) == 2
    assert len(agent) == 13
    assert len(user) == 9
    assert len(infra) == 2


def test_categorize_features():
    """Test the categorize_features function from SDK."""
    probs_dict = {
        "success": 0.85,
        "sentiment_positive": 0.1,
        "sentiment_neutral": 0.77,
        "sentiment_negative": 0.13,
        "loop_behavior": 0.65,
        "incomplete_implementation": 0.45,
        "clarification_or_restatement": 0.30,
        "infrastructure_external_issue": 0.15,
        "unknown_feature": 0.50,
    }

    result = categorize_features(probs_dict)

    # Check sentiment extraction with softmax normalization
    assert result["sentiment"] is not None
    assert result["sentiment"]["predicted"] == "Neutral"
    # Softmax normalizes the probabilities - neutral should be highest
    # but the exact value depends on softmax calculation
    assert result["sentiment"]["probability"] > 0.4  # Should be normalized
    # All sentiment probabilities should sum to ~1.0 after softmax
    all_sentiments = result["sentiment"]["all"]
    total = sum(all_sentiments.values())
    assert abs(total - 1.0) < 0.01  # Should sum to 1.0

    # Check agent behavioral issues (default threshold is 0.2)
    agent_issues = result["agent_behavioral_issues"]
    assert len(agent_issues) == 2  # loop_behavior (0.65) and incomplete_impl (0.45)
    assert agent_issues[0]["name"] == "loop_behavior"
    assert agent_issues[0]["probability"] == 0.65

    # Check user follow-up patterns (clarification_or_restatement is 0.30 > 0.2)
    user_patterns = result["user_followup_patterns"]
    assert len(user_patterns) == 1
    assert user_patterns[0]["name"] == "clarification_or_restatement"

    # Check infrastructure issues (0.15 < 0.2 threshold, so empty)
    infra_issues = result["infrastructure_issues"]
    assert len(infra_issues) == 0

    # Check other/unknown features (0.50 > 0.2)
    other = result["other"]
    assert len(other) == 1
    assert other[0]["name"] == "unknown_feature"


def test_categorize_features_custom_threshold():
    """Test categorize_features with custom threshold."""
    probs_dict = {
        "loop_behavior": 0.65,
        "incomplete_implementation": 0.15,
        "infrastructure_external_issue": 0.10,
    }

    # With threshold 0.0, all features should be included
    result = categorize_features(probs_dict, display_threshold=0.0)
    assert len(result["agent_behavioral_issues"]) == 2
    assert len(result["infrastructure_issues"]) == 1

    # With threshold 0.5, only loop_behavior should be included
    result = categorize_features(probs_dict, display_threshold=0.5)
    assert len(result["agent_behavioral_issues"]) == 1
    assert result["agent_behavioral_issues"][0]["name"] == "loop_behavior"
    assert len(result["infrastructure_issues"]) == 0
