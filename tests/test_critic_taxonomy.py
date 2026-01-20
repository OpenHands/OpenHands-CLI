"""Tests for critic taxonomy."""

from openhands_cli.tui.utils.critic import FEATURE_CATEGORIES, get_category


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
