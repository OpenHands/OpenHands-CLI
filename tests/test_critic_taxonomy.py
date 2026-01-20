"""Tests for critic taxonomy."""

import pytest

from openhands_cli.critic_taxonomy import CriticTaxonomy


def test_feature_counts():
    """Test that we have the expected number of features in each category."""
    # General context features
    assert len(CriticTaxonomy.GENERAL_CONTEXT) == 2

    # Agent behavioral issues
    assert len(CriticTaxonomy.AGENT_BEHAVIORAL_ISSUES) == 13

    # User follow-up patterns
    assert len(CriticTaxonomy.USER_FOLLOWUP_PATTERNS) == 9

    # Infrastructure issues
    assert len(CriticTaxonomy.INFRASTRUCTURE_ISSUES) == 2

    # Behavioral issues = Agent + User
    assert len(CriticTaxonomy.BEHAVIORAL_ISSUES) == 13 + 9

    # All features
    assert len(CriticTaxonomy.ALL_FEATURES) == 2 + 13 + 9 + 2


def test_get_feature_names():
    """Test getting feature names by category."""
    # All features
    all_features = CriticTaxonomy.get_feature_names()
    assert len(all_features) == 26

    # General context
    general = CriticTaxonomy.get_feature_names("general_context")
    assert "user_goal_summary" in general
    assert "overall_sentiment" in general

    # Agent behavioral issues
    agent_issues = CriticTaxonomy.get_feature_names("agent_behavioral_issues")
    assert "misunderstood_intention" in agent_issues
    assert "loop_behavior" in agent_issues

    # User follow-up patterns
    user_patterns = CriticTaxonomy.get_feature_names("user_followup_patterns")
    assert "clarification_or_restatement" in user_patterns
    assert "correction" in user_patterns

    # Behavioral issues (combined)
    behavioral = CriticTaxonomy.get_feature_names("behavioral_issues")
    assert "misunderstood_intention" in behavioral
    assert "clarification_or_restatement" in behavioral

    # Infrastructure issues
    infra = CriticTaxonomy.get_feature_names("infrastructure_issues")
    assert "infrastructure_external_issue" in infra


def test_get_features_by_type():
    """Test getting features by type."""
    # Binary features
    binary = CriticTaxonomy.get_binary_features()
    assert "misunderstood_intention" in binary
    assert "clarification_or_restatement" in binary
    # 13 agent + 8 user (follow_up_timing is classification) + 2 infrastructure
    assert len(binary) == 23

    # Classification features
    classification = CriticTaxonomy.get_classification_features()
    assert "overall_sentiment" in classification
    assert "follow_up_timing" in classification
    assert len(classification) == 2

    # Text features
    text = CriticTaxonomy.get_text_features()
    assert "user_goal_summary" in text
    assert len(text) == 1


def test_user_reply_dependent_features():
    """Test getting features that require user reply."""
    reply_dependent = CriticTaxonomy.get_user_reply_dependent_features()

    # All user follow-up pattern features (except follow_up_timing) require reply
    assert "clarification_or_restatement" in reply_dependent
    assert "correction" in reply_dependent
    assert "frustration_or_complaint" in reply_dependent
    assert len(reply_dependent) == 8

    # Agent behavioral issues should not be in this list
    assert "misunderstood_intention" not in reply_dependent


def test_get_feature_description():
    """Test getting feature descriptions."""
    desc = CriticTaxonomy.get_feature_description("misunderstood_intention")
    assert desc == "Agent misunderstood the user's goal."

    desc = CriticTaxonomy.get_feature_description("loop_behavior")
    assert desc == "Repeated the same failed action ≥3 times."

    with pytest.raises(KeyError):
        CriticTaxonomy.get_feature_description("nonexistent_feature")


def test_validate_feature_value():
    """Test feature value validation."""
    # Binary features
    assert CriticTaxonomy.validate_feature_value("misunderstood_intention", True)
    assert CriticTaxonomy.validate_feature_value("misunderstood_intention", False)
    assert CriticTaxonomy.validate_feature_value("misunderstood_intention", 0)
    assert CriticTaxonomy.validate_feature_value("misunderstood_intention", 1)
    assert not CriticTaxonomy.validate_feature_value("misunderstood_intention", "yes")

    # Classification features
    assert CriticTaxonomy.validate_feature_value("overall_sentiment", "Positive")
    assert CriticTaxonomy.validate_feature_value("overall_sentiment", "Negative")
    assert CriticTaxonomy.validate_feature_value("overall_sentiment", "Neutral")
    assert not CriticTaxonomy.validate_feature_value("overall_sentiment", "Happy")

    assert CriticTaxonomy.validate_feature_value("follow_up_timing", "mid-conversation")
    assert CriticTaxonomy.validate_feature_value("follow_up_timing", "post-completion")
    assert CriticTaxonomy.validate_feature_value("follow_up_timing", "none")
    assert not CriticTaxonomy.validate_feature_value("follow_up_timing", "during")

    # Text features
    assert CriticTaxonomy.validate_feature_value(
        "user_goal_summary", "Fix the bug in login"
    )
    assert not CriticTaxonomy.validate_feature_value("user_goal_summary", 123)

    # Unknown feature
    assert not CriticTaxonomy.validate_feature_value("nonexistent_feature", True)


def test_taxonomy_structure():
    """Test that all features have required fields."""
    for feature_name, spec in CriticTaxonomy.ALL_FEATURES.items():
        # All features must have type and description
        assert "type" in spec, f"{feature_name} missing 'type'"
        assert "description" in spec, f"{feature_name} missing 'description'"

        # Type must be valid
        assert spec["type"] in [
            "binary",
            "classification",
            "text",
        ], f"{feature_name} has invalid type: {spec['type']}"

        # Classification features must have values
        if spec["type"] == "classification":
            assert "values" in spec, (
                f"{feature_name} is classification but missing 'values'"
            )
            assert len(spec["values"]) > 0, f"{feature_name} has empty 'values'"


def test_no_duplicate_features():
    """Test that there are no duplicate feature names across categories."""
    all_names = []
    for category in [
        CriticTaxonomy.GENERAL_CONTEXT,
        CriticTaxonomy.AGENT_BEHAVIORAL_ISSUES,
        CriticTaxonomy.USER_FOLLOWUP_PATTERNS,
        CriticTaxonomy.INFRASTRUCTURE_ISSUES,
    ]:
        all_names.extend(category.keys())

    # Check for duplicates
    assert len(all_names) == len(set(all_names)), "Found duplicate feature names"
