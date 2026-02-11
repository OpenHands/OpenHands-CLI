#!/bin/bash
# Stop hook: runs pre-commit on all files before allowing agent to finish
#
# This hook runs when the agent attempts to stop/finish.
# It can BLOCK the stop by:
#   - Exiting with code 2 (blocked)
#   - Outputting JSON: {"decision": "deny", "additionalContext": "feedback message"}

set -o pipefail

PROJECT_DIR="${OPENHANDS_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" || exit 1

>&2 echo "=== Stop Hook ==="
>&2 echo "Project directory: $PROJECT_DIR"
>&2 echo ""

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
    ESCAPED_OUTPUT=$(echo "$PRECOMMIT_OUTPUT" | jq -Rs .)
    echo "{\"decision\": \"deny\", \"reason\": \"pre-commit failed\", \"additionalContext\": $ESCAPED_OUTPUT}"
    exit 2
fi

>&2 echo "✓ pre-commit passed"
>&2 echo ""
>&2 echo "=== All checks passed, allowing stop ==="
echo '{"decision": "allow"}'
exit 0
