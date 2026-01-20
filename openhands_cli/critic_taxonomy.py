"""Critic taxonomy - mapping of features to categories."""

# Feature to category mapping
FEATURE_CATEGORIES = {
    # General Context & Task Classification
    "user_goal_summary": "general_context",
    "overall_sentiment": "general_context",
    # Agent Behavioral Issues
    "misunderstood_intention": "agent_behavioral_issues",
    "did_not_follow_instruction": "agent_behavioral_issues",
    "insufficient_analysis": "agent_behavioral_issues",
    "insufficient_clarification": "agent_behavioral_issues",
    "improper_tool_use_or_setup": "agent_behavioral_issues",
    "loop_behavior": "agent_behavioral_issues",
    "insufficient_testing": "agent_behavioral_issues",
    "insufficient_debugging": "agent_behavioral_issues",
    "incomplete_implementation": "agent_behavioral_issues",
    "file_management_errors": "agent_behavioral_issues",
    "scope_creep": "agent_behavioral_issues",
    "risky_actions_or_permission": "agent_behavioral_issues",
    "other_agent_issue": "agent_behavioral_issues",
    # User Follow-Up Patterns
    "follow_up_timing": "user_followup_patterns",
    "clarification_or_restatement": "user_followup_patterns",
    "correction": "user_followup_patterns",
    "direction_change": "user_followup_patterns",
    "vcs_update_requests": "user_followup_patterns",
    "progress_or_scope_concern": "user_followup_patterns",
    "frustration_or_complaint": "user_followup_patterns",
    "removal_or_reversion_request": "user_followup_patterns",
    "other_user_issue": "user_followup_patterns",
    # Infrastructure Issues
    "infrastructure_external_issue": "infrastructure_issues",
    "infrastructure_agent_caused_issue": "infrastructure_issues",
}


def get_category(feature_name: str) -> str | None:
    """Get the category for a feature.

    Args:
        feature_name: Name of the feature

    Returns:
        Category name or None if not found
    """
    return FEATURE_CATEGORIES.get(feature_name)
