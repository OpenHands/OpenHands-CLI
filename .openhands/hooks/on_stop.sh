#!/bin/bash
# Stop hook: runs pre-commit on all files before allowing agent to finish
#
# This hook runs when the agent attempts to stop/finish.
# It can BLOCK the stop by:
#   - Exiting with code 2 (blocked)
#   - Outputting JSON: {"decision": "deny", "additionalContext": "feedback message"}

set -o pipefail

# Escape a string for JSON (fallback when jq is not available)
json_escape() {
    local str="$1"
    str="${str//\\/\\\\}"      # Escape backslashes first
    str="${str//\"/\\\"}"      # Escape double quotes
    str="${str//$'\n'/\\n}"    # Escape newlines
    str="${str//$'\r'/\\r}"    # Escape carriage returns
    str="${str//$'\t'/\\t}"    # Escape tabs
    echo "\"$str\""
}

PROJECT_DIR="${OPENHANDS_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" || {
    # Fail silently - approve but include the reason for potential error display
    >&2 echo "⚠️  Failed to cd to project directory: $PROJECT_DIR, skipping checks"
    echo "{\"decision\": \"allow\", \"reason\": \"Invalid project directory - hook skipped\"}"
    exit 0
}

>&2 echo "=== Stop Hook ==="
>&2 echo "Project directory: $PROJECT_DIR"
>&2 echo ""

# --------------------------
# Check if pre-commit is available
# --------------------------
PRECOMMIT_AVAILABLE=false
if command -v uv &> /dev/null; then
    # Check if pre-commit is available via uv
    if uv run pre-commit --version &> /dev/null; then
        PRECOMMIT_AVAILABLE=true
    fi
elif command -v pre-commit &> /dev/null; then
    PRECOMMIT_AVAILABLE=true
fi

if [ "$PRECOMMIT_AVAILABLE" = false ]; then
    # Fail silently - approve but include the reason for potential error display
    >&2 echo "⚠️  pre-commit is not installed, skipping checks"
    echo "{\"decision\": \"allow\", \"reason\": \"pre-commit not installed - hook skipped\"}"
    exit 0
fi

# --------------------------
# Run pre-commit on all files
# --------------------------
>&2 echo "=== Running pre-commit run --all-files ==="
if command -v uv &> /dev/null; then
    PRECOMMIT_OUTPUT=$(uv run pre-commit run --all-files 2>&1)
    PRECOMMIT_EXIT=$?
else
    PRECOMMIT_OUTPUT=$(pre-commit run --all-files 2>&1)
    PRECOMMIT_EXIT=$?
fi

>&2 echo "$PRECOMMIT_OUTPUT"

if [ $PRECOMMIT_EXIT -ne 0 ]; then
    >&2 echo "⚠️  pre-commit found issues (exit code: $PRECOMMIT_EXIT)"
    >&2 echo "=== BLOCKING STOP: Issues found ==="
    # Use jq if available, otherwise fall back to bash-based escaping
    if command -v jq &> /dev/null; then
        ESCAPED_OUTPUT=$(echo "$PRECOMMIT_OUTPUT" | jq -Rs .)
    else
        ESCAPED_OUTPUT=$(json_escape "$PRECOMMIT_OUTPUT")
    fi
    echo "{\"decision\": \"deny\", \"reason\": \"pre-commit failed\", \"additionalContext\": $ESCAPED_OUTPUT}"
    exit 2
fi

>&2 echo "✓ pre-commit passed"
>&2 echo ""
>&2 echo "=== All checks passed, allowing stop ==="
echo '{"decision": "allow"}'
exit 0
