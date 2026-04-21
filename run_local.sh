#!/usr/bin/env bash
# run_local.sh — launch the OpenHands CLI with the local openhands-sdk editable install.
#
# Usage:  ./run_local.sh
#
# Why this exists: `uv run openhands` re-syncs from uv.lock before launching,
# which reinstalls the published openhands-sdk and wipes the local editable
# install needed for the Databricks provider.  This script re-installs the
# local SDK in compat mode (so pyright can trace it too) and then launches
# the CLI with --no-sync to prevent uv from touching the venv again.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_PATH="$SCRIPT_DIR/../software-agent-sdk/openhands-sdk"

# Load local developer overrides (e.g. internal pip/npm/go proxy settings).
# Create .local.env next to this script — it is gitignored and never committed.
# Example .local.env:
#   UV_INDEX_URL=https://pypi-proxy.dev.databricks.com/simple
if [[ -f "$SCRIPT_DIR/.local.env" ]]; then
    echo "==> Loading local env overrides from .local.env..."
    set -a
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.local.env"
    set +a
fi

if [[ ! -d "$SDK_PATH" ]]; then
    echo "ERROR: local SDK not found at $SDK_PATH"
    echo "       Clone software-agent-sdk next to OpenHands-CLI and try again."
    exit 1
fi

echo "==> Installing local openhands-sdk (compat editable mode)..."
uv pip install \
    --python "$SCRIPT_DIR/.venv/bin/python" \
    -e "$SDK_PATH" \
    --config-settings editable_mode=compat

# databricks-sdk is needed for U2M (browser SSO) and CLI Profile auth.
# It is an optional dep — install it here so both auth methods work out
# of the box without a separate manual step.
echo "==> Ensuring databricks-sdk is installed (needed for U2M / profile auth)..."
if ! "$SCRIPT_DIR/.venv/bin/python" -c "import databricks.sdk" 2>/dev/null; then
    uv pip install \
        --python "$SCRIPT_DIR/.venv/bin/python" \
        "databricks-sdk"
    echo "    installed databricks-sdk"
else
    echo "    already present"
fi

echo "==> Verifying install..."
SDK_FILE=$("$SCRIPT_DIR/.venv/bin/python" -c \
    "import openhands.sdk; print(openhands.sdk.__file__)")

if echo "$SDK_FILE" | grep -q "site-packages"; then
    echo "ERROR: install did not take — still using published package:"
    echo "       $SDK_FILE"
    exit 1
fi

echo "    OK: $SDK_FILE"
echo ""
echo "==> Launching OpenHands CLI (direct venv, no uv run)..."
# Use .venv/bin/openhands directly to guarantee the venv Python is used.
# `uv run --no-sync` can pick up an active conda/system env (visible as
# "(openhands) (base)" in the shell prompt) instead of the local .venv,
# which would load the published openhands-sdk and lose DatabricksLLM.
exec "$SCRIPT_DIR/.venv/bin/openhands" "$@"
