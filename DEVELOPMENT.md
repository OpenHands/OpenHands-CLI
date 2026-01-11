# Development Guide

This guide covers setting up a local development environment for the OpenHands CLI.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

Install uv if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart your shell so "uv" is on PATH, or follow the installer hint
```

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/All-Hands-AI/OpenHands-CLI.git
   cd OpenHands-CLI
   ```

2. Install dependencies:

   ```bash
   make install-dev
   ```

3. Install pre-commit hooks:

   ```bash
   uv run pre-commit install
   ```

## Running Locally

```bash
# Start the CLI
make run
# or
uv run openhands
```

## Building a Standalone Executable

```bash
# Build (installs PyInstaller if needed)
./build.sh --install-pyinstaller

# The binary will be in dist/
./dist/openhands            # macOS/Linux
# dist/openhands.exe        # Windows
```

## Testing

```bash
# Run all tests
make test

# Run specific tests
uv run pytest tests/test_cli_help.py -v
```

## Linting

Always run lint before committing changes:

```bash
make lint
```

## Code Style

The project uses:
- [ruff](https://docs.astral.sh/ruff/) for formatting and linting
- [pyright](https://github.com/microsoft/pyright) for type checking
- [pre-commit](https://pre-commit.com/) hooks for automated checks

When using types, prefer modern typing syntax (e.g., use `| None` instead of `Optional`).

## Snapshot Testing

The CLI uses [pytest-textual-snapshot](https://github.com/Textualize/pytest-textual-snapshot) for visual regression testing of Textual UI components.

```bash
# Run snapshot tests
uv run pytest tests/snapshots/ -v

# Update snapshots when intentional UI changes are made
uv run pytest tests/snapshots/ --snapshot-update
```

See the repository instructions for more details on writing and viewing snapshot tests.
