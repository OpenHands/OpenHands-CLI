# OpenHands CLI 🎛️

OpenHands CLI is a fast, extensible command-line client for OpenHands AI Agents. It provides:

- A full Terminal User Interface (TUI) for interactive sessions
- Headless and automation modes for scripted runs and CI
- An Agent Client Protocol (ACP) surface for editor and tooling integrations
- Packaging support to build a standalone executable

This README highlights the most common ways to run and integrate the CLI (ACP, editors, development with `uv`, and building a binary).

---

## Quicklinks

- Usage & Quick Start
- ACP (editor integration)
- Standalone binary (PyInstaller)
- Features
- Contributing

---

## Table of contents

1. [Quick start](#quick-start)
2. [ACP (Agent Client Protocol)](#acp-agent-client-protocol)
3. [Standalone binary (PyInstaller)](#standalone-binary-pyinstaller)
4. [Features](#features)
5. [Contributing](#contributing)
6. [Files of interest](#files-of-interest)

---

## Quick start

Recommended for development: run from source using `uv`.

### Run the TUI (development)

Open a PowerShell and run:

```powershell
# run from source
uv run python -m openhands_cli.simple_main

# or, if the environment exposes the entrypoint
uv run openhands
```

Notes:
- The project targets Python 3.12. See `DEVELOPMENT.md` for environment setup using `uv`.

- `uv` is used here to ensure pinned dependencies and repeatable commands.

### Run headless (automation)

```powershell
uv run python -m openhands_cli.simple_main --headless --script my_script.json
```

Replace `--script my_script.json` with your automation arguments (see the CLI help for available flags).

---

## ACP (Agent Client Protocol)

ACP lets editors, language servers, and other tools control OpenHands via JSON-RPC. Use the helper scripts in `scripts/acp/` to experiment.

Examples:

```powershell
# Run the interactive JSON-RPC CLI against the source runner
uv run python scripts/acp/jsonrpc_cli.py ./dist/openhands acp

# Debug client
uv run python scripts/acp/debug_client.py
```

The ACP implementation lives in `openhands_cli/acp_impl/` — see unit tests under `tests/acp/` for integration examples.

---

## Standalone binary (PyInstaller)

We include a PyInstaller spec file (`openhands-cli.spec`) and a convenience build helper (`build.py`) to produce a single-platform executable in `dist/`.

Quick build steps (developer machine):

```powershell
# Ensure you have uv and the dev deps
# (see DEVELOPMENT.md for environment setup)

uv add --dev pyinstaller
uv run python build.py

# After the build, check the `dist/` directory for the generated binary
ls .\dist\
```

If you need to customize packaging behavior, inspect `openhands-cli.spec` and `build.py`.

---

## Features

- Interactive Terminal User Interface (TUI) with visualizer and session controls
- Headless automation mode for scripted workflows and CI
- ACP (Agent Client Protocol) for editor/tool integrations (JSON-RPC)
- Standalone packaging via PyInstaller for easy distribution
- Test coverage and examples under `tests/` and `tests/acp/`

---

## Contributing

We love contributions. A quick path to start:

1. Read `DEVELOPMENT.md` to set up `uv` and a development environment.
2. Run the test suite locally:

```powershell
uv run pytest -q
```

3. Add tests for any behavior you change or add (see `tests/` and `tests/acp/`).
4. For packaging changes, update `build.py` and the spec file `openhands-cli.spec`.
5. Open a PR against the `main` branch and include a short description of the change and test plan.

If you want a guided starter task, open an issue and tag it `good-first-issue`.

---

## Files of interest

- `build.py` — convenience script that wraps PyInstaller for local builds
- `openhands-cli.spec` — PyInstaller spec used by the build process
- `scripts/acp/` — ACP helper scripts and debug client
- `openhands_cli/simple_main.py` — main module for running the CLI from source
- `DEVELOPMENT.md` — detailed dev environment setup and `uv` instructions

---

Thank you for exploring OpenHands! If something in this README is out of date, please open a PR or issue — we try to keep quick-start paths accurate and small.
