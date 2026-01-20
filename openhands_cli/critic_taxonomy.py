"""Comprehensive taxonomy of Critic Rubrics features.

This taxonomy is derived from production traces and defines the features used
for critic evaluation and user follow-up prediction.
"""

from typing import ClassVar, Literal


# Type definitions for feature values
OverallSentiment = Literal["Positive", "Negative", "Neutral"]
FollowUpTiming = Literal["mid-conversation", "post-completion", "none"]


class CriticTaxonomy:
    """Taxonomy of features for critic evaluation and prediction."""

    # ========================================================================
    # General Context & Task Classification
    # ========================================================================

    GENERAL_CONTEXT: ClassVar[dict] = {
        "user_goal_summary": {
            "type": "text",
            "description": "One-sentence summary of user intent.",
        },
        "overall_sentiment": {
            "type": "classification",
            "description": "User sentiment: Positive / Negative / Neutral.",
            "values": ["Positive", "Negative", "Neutral"],
        },
    }

    # ========================================================================
    # Behavioral Issues (Agent + User Follow-Up Patterns)
    # ========================================================================

    # Agent Behavioral Issues
    AGENT_BEHAVIORAL_ISSUES: ClassVar[dict] = {
        "misunderstood_intention": {
            "type": "binary",
            "description": "Agent misunderstood the user's goal.",
        },
        "did_not_follow_instruction": {
            "type": "binary",
            "description": "Agent ignored explicit instructions.",
        },
        "insufficient_analysis": {
            "type": "binary",
            "description": "Agent failed to inspect relevant prior code/docs.",
        },
        "insufficient_clarification": {
            "type": "binary",
            "description": "Agent acted despite ambiguous requirements.",
        },
        "improper_tool_use_or_setup": {
            "type": "binary",
            "description": "Misused tools or had incorrect dependencies/config.",
        },
        "loop_behavior": {
            "type": "binary",
            "description": "Repeated the same failed action ≥3 times.",
        },
        "insufficient_testing": {
            "type": "binary",
            "description": "Skipped reasonable validation or test runs.",
        },
        "insufficient_debugging": {
            "type": "binary",
            "description": "Ignored or failed to debug observed failures.",
        },
        "incomplete_implementation": {
            "type": "binary",
            "description": "Delivered incomplete or nonfunctional code.",
        },
        "file_management_errors": {
            "type": "binary",
            "description": "Created or modified files incorrectly.",
        },
        "scope_creep": {
            "type": "binary",
            "description": "Added unrequested functionality.",
        },
        "risky_actions_or_permission": {
            "type": "binary",
            "description": "Performed risky actions without explicit approval.",
        },
        "other_agent_issue": {
            "type": "binary",
            "description": "Other agent-side failure not covered above.",
        },
    }

    # User Follow-Up Patterns (requires user reply)
    USER_FOLLOWUP_PATTERNS: ClassVar[dict] = {
        "follow_up_timing": {
            "type": "classification",
            "description": (
                "When user replied: mid-conversation / post-completion / none."
            ),
            "values": ["mid-conversation", "post-completion", "none"],
            "note": "Applies only when a user replies after the agent finishes.",
        },
        "clarification_or_restatement": {
            "type": "binary",
            "description": "User clarifies or restates earlier intent.",
            "requires_user_reply": True,
        },
        "correction": {
            "type": "binary",
            "description": "User corrects technical or procedural error.",
            "requires_user_reply": True,
        },
        "direction_change": {
            "type": "binary",
            "description": "User adds constraints or redirects scope.",
            "requires_user_reply": True,
        },
        "vcs_update_requests": {
            "type": "binary",
            "description": "User requests forward VCS actions (commit, push, merge).",
            "requires_user_reply": True,
        },
        "progress_or_scope_concern": {
            "type": "binary",
            "description": "User flags slowness or excessive scope.",
            "requires_user_reply": True,
        },
        "frustration_or_complaint": {
            "type": "binary",
            "description": "User expresses dissatisfaction or annoyance.",
            "requires_user_reply": True,
        },
        "removal_or_reversion_request": {
            "type": "binary",
            "description": "User requests to undo or revert prior work.",
            "requires_user_reply": True,
        },
        "other_user_issue": {
            "type": "binary",
            "description": "Any other user-side concern.",
            "requires_user_reply": True,
        },
    }

    # ========================================================================
    # Infrastructure Issues
    # ========================================================================

    INFRASTRUCTURE_ISSUES: ClassVar[dict] = {
        "infrastructure_external_issue": {
            "type": "binary",
            "description": "External environment or platform failure.",
        },
        "infrastructure_agent_caused_issue": {
            "type": "binary",
            "description": "Infrastructure fault caused by prior agent actions.",
        },
    }

    # ========================================================================
    # Grouped Features
    # ========================================================================

    # Group agent behavioral issues with user follow-up patterns
    BEHAVIORAL_ISSUES: ClassVar[dict] = {
        **AGENT_BEHAVIORAL_ISSUES,
        **USER_FOLLOWUP_PATTERNS,
    }

    # All features combined
    ALL_FEATURES: ClassVar[dict] = {
        **GENERAL_CONTEXT,
        **BEHAVIORAL_ISSUES,
        **INFRASTRUCTURE_ISSUES,
    }

    @classmethod
    def get_feature_names(cls, category: str | None = None) -> list[str]:
        """Get list of feature names for a category or all features.

        Args:
            category: Feature category name (general_context, behavioral_issues,
                     agent_behavioral_issues, user_followup_patterns,
                     infrastructure_issues) or None for all features.

        Returns:
            List of feature names.
        """
        category_map = {
            "general_context": cls.GENERAL_CONTEXT,
            "behavioral_issues": cls.BEHAVIORAL_ISSUES,
            "agent_behavioral_issues": cls.AGENT_BEHAVIORAL_ISSUES,
            "user_followup_patterns": cls.USER_FOLLOWUP_PATTERNS,
            "infrastructure_issues": cls.INFRASTRUCTURE_ISSUES,
        }

        if category is None:
            return list(cls.ALL_FEATURES.keys())

        if category not in category_map:
            raise ValueError(
                f"Unknown category: {category}. "
                f"Valid categories: {list(category_map.keys())}"
            )

        return list(category_map[category].keys())

    @classmethod
    def get_binary_features(cls) -> list[str]:
        """Get all binary feature names."""
        return [
            name for name, spec in cls.ALL_FEATURES.items() if spec["type"] == "binary"
        ]

    @classmethod
    def get_classification_features(cls) -> list[str]:
        """Get all classification feature names."""
        return [
            name
            for name, spec in cls.ALL_FEATURES.items()
            if spec["type"] == "classification"
        ]

    @classmethod
    def get_text_features(cls) -> list[str]:
        """Get all text feature names."""
        return [
            name for name, spec in cls.ALL_FEATURES.items() if spec["type"] == "text"
        ]

    @classmethod
    def get_user_reply_dependent_features(cls) -> list[str]:
        """Get features that require user reply to be meaningful."""
        return [
            name
            for name, spec in cls.ALL_FEATURES.items()
            if spec.get("requires_user_reply", False)
        ]

    @classmethod
    def get_feature_description(cls, feature_name: str) -> str:
        """Get description for a feature.

        Args:
            feature_name: Name of the feature.

        Returns:
            Feature description.

        Raises:
            KeyError: If feature name is not found.
        """
        if feature_name not in cls.ALL_FEATURES:
            raise KeyError(f"Unknown feature: {feature_name}")
        return cls.ALL_FEATURES[feature_name]["description"]

    @classmethod
    def validate_feature_value(cls, feature_name: str, value) -> bool:
        """Validate a feature value against the taxonomy.

        Args:
            feature_name: Name of the feature.
            value: Value to validate.

        Returns:
            True if valid, False otherwise.
        """
        if feature_name not in cls.ALL_FEATURES:
            return False

        spec = cls.ALL_FEATURES[feature_name]
        feature_type = spec["type"]

        if feature_type == "binary":
            return isinstance(value, bool) or value in (0, 1)
        elif feature_type == "classification":
            return value in spec.get("values", [])
        elif feature_type == "text":
            return isinstance(value, str)
        else:
            return False
