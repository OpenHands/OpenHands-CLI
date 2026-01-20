# Critic Taxonomy

This document describes the comprehensive taxonomy for critic rubrics used in the OpenHands CLI.

## Overview

The taxonomy defines 26 features organized into 4 main categories for evaluating agent performance and predicting user follow-up patterns. The taxonomy is based on production trace analysis.

## Feature Categories

### 1. General Context & Task Classification (2 features)

**Text Features:**
- `user_goal_summary`: One-sentence summary of user intent

**Classification Features:**
- `overall_sentiment`: User sentiment (Positive / Negative / Neutral)

### 2. Agent Behavioral Issues (13 binary features)

These features identify problems in agent behavior:

- `misunderstood_intention`: Agent misunderstood the user's goal
- `did_not_follow_instruction`: Agent ignored explicit instructions
- `insufficient_analysis`: Agent failed to inspect relevant prior code/docs
- `insufficient_clarification`: Agent acted despite ambiguous requirements
- `improper_tool_use_or_setup`: Misused tools or had incorrect dependencies/config
- `loop_behavior`: Repeated the same failed action ≥3 times
- `insufficient_testing`: Skipped reasonable validation or test runs
- `insufficient_debugging`: Ignored or failed to debug observed failures
- `incomplete_implementation`: Delivered incomplete or nonfunctional code
- `file_management_errors`: Created or modified files incorrectly
- `scope_creep`: Added unrequested functionality
- `risky_actions_or_permission`: Performed risky actions without explicit approval
- `other_agent_issue`: Other agent-side failure not covered above

### 3. User Follow-Up Patterns (9 features)

These features apply only when a user replies after the agent finishes:

**Classification:**
- `follow_up_timing`: When user replied (mid-conversation / post-completion / none)

**Binary Features (all require user reply):**
- `clarification_or_restatement`: User clarifies or restates earlier intent
- `correction`: User corrects technical or procedural error
- `direction_change`: User adds constraints or redirects scope
- `vcs_update_requests`: User requests forward VCS actions (commit, push, merge)
- `progress_or_scope_concern`: User flags slowness or excessive scope
- `frustration_or_complaint`: User expresses dissatisfaction or annoyance
- `removal_or_reversion_request`: User requests to undo or revert prior work
- `other_user_issue`: Any other user-side concern

### 4. Infrastructure Issues (2 binary features)

- `infrastructure_external_issue`: External environment or platform failure
- `infrastructure_agent_caused_issue`: Infrastructure fault caused by prior agent actions

## Grouped Features

The taxonomy provides two logical groupings:

### BEHAVIORAL_ISSUES (22 features)
Combines Agent Behavioral Issues + User Follow-Up Patterns for prediction tasks.

### ALL_FEATURES (26 features)
Complete taxonomy including all categories.

## Usage

```python
from openhands_cli.critic_taxonomy import CriticTaxonomy

# Get all feature names
all_features = CriticTaxonomy.get_feature_names()

# Get features by category
agent_issues = CriticTaxonomy.get_feature_names("agent_behavioral_issues")
user_patterns = CriticTaxonomy.get_feature_names("user_followup_patterns")
behavioral = CriticTaxonomy.get_feature_names("behavioral_issues")

# Get features by type
binary_features = CriticTaxonomy.get_binary_features()  # 23 features
classification_features = CriticTaxonomy.get_classification_features()  # 2 features
text_features = CriticTaxonomy.get_text_features()  # 1 feature

# Get features that require user reply
reply_dependent = CriticTaxonomy.get_user_reply_dependent_features()  # 8 features

# Get feature description
desc = CriticTaxonomy.get_feature_description("loop_behavior")
# Returns: "Repeated the same failed action ≥3 times."

# Validate feature values
is_valid = CriticTaxonomy.validate_feature_value("overall_sentiment", "Positive")  # True
is_valid = CriticTaxonomy.validate_feature_value("loop_behavior", True)  # True
is_valid = CriticTaxonomy.validate_feature_value("overall_sentiment", "Happy")  # False
```

## Feature Distribution

- **Binary features**: 23
  - Agent behavioral: 13
  - User follow-up (excluding timing): 8
  - Infrastructure: 2

- **Classification features**: 2
  - overall_sentiment (3 values)
  - follow_up_timing (3 values)

- **Text features**: 1
  - user_goal_summary

## Implementation Notes

1. **User reply dependency**: 8 features are marked with `requires_user_reply=True` and should only be evaluated when a user has replied after agent completion.

2. **Feature grouping**: Agent behavioral issues and user follow-up patterns are grouped together in `BEHAVIORAL_ISSUES` for joint prediction tasks.

3. **Validation**: Use `validate_feature_value()` to ensure feature values match the expected type and constraints.

4. **Extensibility**: The taxonomy uses ClassVar dictionaries for type safety and can be extended by adding new features to the appropriate category.
