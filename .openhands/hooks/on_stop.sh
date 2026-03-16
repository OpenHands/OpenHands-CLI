#!/bin/bash
# Stop hook: runs pre-commit on all files before allowing agent to finish

set -o pipefail

PROJECT_DIR="${OPENHANDS_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" || {
    >&2 echo "⚠️  Failed to cd to project directory: $PROJECT_DIR, skipping checks"
    echo '{"decision": "allow", "reason": "Invalid project directory - hook skipped"}'
    exit 0
}

>&2 echo "=== Stop Hook: Running pre-commit ==="

# Check if pre-commit is available
if command -v uv &> /dev/null && uv run pre-commit --version &> /dev/null; then
    PRECOMMIT_CMD="uv run pre-commit"
elif command -v pre-commit &> /dev/null; then
    PRECOMMIT_CMD="pre-commit"
else
    >&2 echo "⚠️  pre-commit is not installed, skipping checks"
    echo '{"decision": "allow", "reason": "pre-commit not installed - hook skipped"}'
    exit 0
fi

# Run pre-commit
PRECOMMIT_OUTPUT=$($PRECOMMIT_CMD run --all-files 2>&1)
PRECOMMIT_EXIT=$?
>&2 echo "$PRECOMMIT_OUTPUT"

if [ $PRECOMMIT_EXIT -ne 0 ]; then
    >&2 echo "=== BLOCKING STOP: pre-commit failed ==="
    ESCAPED_OUTPUT=$(python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" <<< "$PRECOMMIT_OUTPUT")
    echo "{\"decision\": \"deny\", \"reason\": \"pre-commit failed\", \"additionalContext\": $ESCAPED_OUTPUT}"
    exit 2
fi

>&2 echo "=== All checks passed ==="
echo '{"decision": "allow"}'
