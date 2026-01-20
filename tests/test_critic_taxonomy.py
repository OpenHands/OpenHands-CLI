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

    # Check sentiment extraction
    assert result["sentiment"] is not None
    assert result["sentiment"]["predicted"] == "Neutral"
    assert result["sentiment"]["probability"] == 0.77

    # Check agent behavioral issues
    agent_issues = result["agent_behavioral_issues"]
    assert len(agent_issues) == 2
    assert agent_issues[0]["name"] == "loop_behavior"
    assert agent_issues[0]["probability"] == 0.65

    # Check user follow-up patterns
    user_patterns = result["user_followup_patterns"]
    assert len(user_patterns) == 1
    assert user_patterns[0]["name"] == "clarification_or_restatement"

    # Check infrastructure issues
    infra_issues = result["infrastructure_issues"]
    assert len(infra_issues) == 1
    assert infra_issues[0]["name"] == "infrastructure_external_issue"

    # Check other/unknown features
    other = result["other"]
    assert len(other) == 1
    assert other[0]["name"] == "unknown_feature"
