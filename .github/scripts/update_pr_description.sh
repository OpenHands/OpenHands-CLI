#!/bin/bash

# Script to update PR description with uvx launch instructions
# Requires environment variables: GH_TOKEN, PR_NUMBER, REPO, SHORT_SHA

set -e

# Check required environment variables
if [[ -z "$GH_TOKEN" || -z "$PR_NUMBER" || -z "$REPO" ]]; then
    echo "Error: Missing required environment variables"
    echo "Required: GH_TOKEN, PR_NUMBER, REPO"
    exit 1
fi

# Get the PR head branch name (the source branch of the PR)
BRANCH_NAME=$(gh api repos/$REPO/pulls/$PR_NUMBER --jq '.head.ref')
echo "PR source branch: $BRANCH_NAME"

# Get current PR description
echo "Fetching current PR description..."
CURRENT_DESCRIPTION=$(gh api repos/$REPO/pulls/$PR_NUMBER --jq '.body // ""')

# Create the simplified uvx instruction section
UVX_SECTION="

---

## 🚀 Try this PR

\`\`\`bash
uvx --python 3.12 git+https://github.com/$REPO.git@$BRANCH_NAME
\`\`\`"

# Check if the uvx section already exists in the description
if echo "$CURRENT_DESCRIPTION" | grep -q "## 🚀 Try this PR"; then
    echo "uvx section already exists in PR description, updating it..."
    # Remove existing uvx section and add new one
    UPDATED_DESCRIPTION=$(echo "$CURRENT_DESCRIPTION" | sed '/## 🚀 Try this PR/,$d')
    UPDATED_DESCRIPTION="$UPDATED_DESCRIPTION$UVX_SECTION"
else
    echo "Adding uvx section to PR description..."
    # Append the uvx section to existing description
    UPDATED_DESCRIPTION="$CURRENT_DESCRIPTION$UVX_SECTION"
fi

# Update the PR description
echo "Updating PR description..."
gh api repos/$REPO/pulls/$PR_NUMBER \
    --method PATCH \
    --field body="$UPDATED_DESCRIPTION"

echo "PR description updated successfully!"