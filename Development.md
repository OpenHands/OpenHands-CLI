# Development Guide

This guide is for contributors editing source code in OpenHands CLI.

For the shared OpenHands contribution process, start with
[CONTRIBUTING.md](CONTRIBUTING.md). That file points to the canonical
OpenHands-wide contributor guide. This document is the repo-specific companion
for local setup, TUI development, testing, and packaging workflows.

## What lives in this repo

OpenHands CLI includes:

- the main Textual TUI (`openhands`)
- the browser-served Textual view (`openhands web`)
- the ACP entrypoint (`openhands-acp`)
- packaging for the standalone executable (`openhands-cli.spec`, `build.sh`)
- CLI-specific tests, snapshots, and end-to-end coverage

## Prerequisites

- Python 3.12
- `uv` 0.11.6 or newer
- Git
- `tmux` is recommended for interactive TUI work so you can detach and resume
  sessions

If `uv` is not installed yet, use:

```bash
make install-uv
```

## Initial setup

```bash
git clone https://github.com/<your-user>/openhands-cli.git
cd openhands-cli
make build
```

`make build` will:

- verify your `uv` version
- install development dependencies with `uv sync --dev`
- install pre-commit hooks

## Repository layout

```text
openhands-cli/
├── openhands_cli/      # CLI, TUI, ACP, auth, MCP, cloud integrations
├── tests/              # Unit, integration, and snapshot-adjacent tests
├── tui_e2e/            # End-to-end tests against the packaged executable
├── scripts/            # Development helpers
├── hooks/              # PyInstaller/runtime hooks
├── build.sh            # Binary build entrypoint
├── openhands-cli.spec  # PyInstaller spec file
└── Makefile            # Common development commands
```

Important source areas:

- `openhands_cli/tui/` for Textual widgets, screens, styling, and layout
- `openhands_cli/auth/` for authentication flows
- `openhands_cli/mcp/` for MCP configuration and UX
- `openhands_cli/cloud/` for cloud-specific behavior
- `openhands_cli/conversations/` for conversation management

## Daily development workflow

### Recommended fast loop for TUI work

```bash
make run-watch
```

This is the fastest iteration path for most TUI changes. It watches
`openhands_cli/` and restarts the app when `.py` or `.tcss` files change.

### Other useful run modes

```bash
make run
```

Runs the normal interactive TUI.

```bash
uv run openhands --exit-without-confirmation
```

Useful for automation-driven runs. Once the TUI is active, quit with `Ctrl+Q`.
`Ctrl+C` is usually not enough.

```bash
openhands web
```

Runs the browser-served Textual view.

```bash
uv run openhands-acp
```

Runs the ACP entrypoint.

## Code quality

### Formatting and linting

```bash
make lint
make format
uv run pre-commit run --all-files
```

Notes:

- `make lint` is a fast Ruff-only pass over `openhands_cli/`.
- `make format` formats Python files under `openhands_cli/`.
- `uv run pre-commit run --all-files` is the closest local match to the lint CI
  job and is the better final check before pushing, especially when you touch
  files outside `openhands_cli/`.

### Typing

```bash
uv run pyright
```

Use modern Python typing in new code where practical:

- prefer `X | None` over `Optional[X]`
- add type hints on new public functions and interfaces
- run `uv run pyright` for Python feature work, refactors, and bug fixes that
  could affect typed interfaces

## Testing

OpenHands CLI has multiple testing layers. The right validation depends on what
kind of change you made.

### Standard test suite

```bash
make test
```

This runs the main pytest suite and skips snapshot tests.

Use this for:

- business logic changes
- command handling changes
- non-visual CLI behavior
- refactors in `openhands_cli/` that do not alter rendering

### Snapshot tests

```bash
make test-snapshots
```

Snapshot tests are the primary visual regression checks for the Textual UI.
Run them when you change:

- widget layout
- styling or `.tcss`
- screen composition
- rendered output in the TUI

If the UI change is intentional, update snapshots with:

```bash
uv run pytest tests/snapshots --snapshot-update
```

Snapshot files live under:

- `tests/snapshots/__snapshots__/test_app_snapshots/`
- `tests/snapshots/__snapshots__/test_visualizer_snapshots/`

When adding new snapshot tests:

- keep terminal size fixed
- mock external dependencies so output stays deterministic
- prefer targeted unit tests alongside snapshots when the logic is non-visual

### Binary end-to-end tests

For authoritative binary validation, use the build script:

```bash
./build.sh --install-pyinstaller
```

That command builds the standalone executable and then runs the `tui_e2e`
runner against the built `dist/` binary. It is the right check for changes that
affect:

- packaging or startup
- ACP flows
- auth and connection flows
- end-to-end CLI behavior
- code paths that differ between source execution and the frozen binary

If you already have a fresh `dist/` build and only want to rerun the binary test
runner, use:

```bash
uv run python build.py --no-build
```

`make test-binary` currently runs `pytest tui_e2e`, which is useful while
editing the `tui_e2e` modules themselves, but it is not the best pass/fail gate
for feature or bug-fix validation because the authoritative binary checks live
in `build.py`.

Binary tests can use a mock OpenAI-compatible LLM server for deterministic test
runs. When configuring the mock model, use `openai/gpt-4o-mock` so LiteLLM sees
an explicit provider prefix.

### Which checks should I run?

As a rule of thumb:

- docs-only changes: run `uv run pre-commit run --files <changed-docs>`
- Python logic changes: run `make test` and `uv run pyright`
- TUI or styling changes: run `make test`, `make test-snapshots`, and `uv run pyright`
- binary, ACP, auth, or packaging changes: run `make test`, `uv run pyright`, and `./build.sh --install-pyinstaller`
- broad changes: run the relevant checks above rather than relying on a single catch-all command

## Building the standalone executable

```bash
./build.sh --install-pyinstaller
```

Use this when you touch:

- `openhands-cli.spec`
- `hooks/`
- runtime packaging behavior
- assets or imports that may behave differently in a frozen binary

If a dependency works in source mode but not in the executable, inspect:

- hidden imports in `openhands-cli.spec`
- PyInstaller hooks in `hooks/`
- whether the affected code uses dynamic imports or runtime-discovered assets

## Pull requests

Before opening a PR, make sure you have:

1. kept the scope focused
2. run the relevant validation for the code you changed
3. documented manual testing for user-facing changes
4. included screenshots or snapshot updates for TUI changes when appropriate

The PR template expects:

- why the change is needed
- a short summary of what changed
- issue reference(s)
- explicit test steps
- screenshots or video for UI changes when relevant

## When to update which document

- update `CONTRIBUTING.md` only when the repo-specific contributor entrypoint
  needs to change
- update the shared OpenHands contributor guidance in the docs repo when the
  process should apply across repositories
- update this `Development.md` when the local setup, testing workflow, TUI
  development loop, or packaging guidance for OpenHands CLI changes

## Need help?

- Open an issue in this repository
- Join Slack: https://openhands.dev/joinslack
